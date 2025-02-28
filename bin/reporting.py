#!/usr/bin/env python3

import argparse
import pickle
from json import dump
from os import system
from pysam import VariantFile
from pysam import bcftools
from pysam import tabix_compress
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

def parse_args():
    """Parse input arguments.

    Keyword arguments:

    -v, --VCF       -- input sample VCF file
    -s, --SAMPLE_ID -- sample id

    Return:

    args -- the parsed arguments
    """
    parser = argparse.ArgumentParser(
        description = 'annotations using CADD, REVEL, and gnomAD 2.1.1'
    )
    parser.add_argument(
        '-v',
        metavar = '--VCF',
        type = str,
        help = 'The input sample vcf',
        required = True
    )
    parser.add_argument(
        '-s',
        metavar = '--SAMPLE_ID',
        type = str,
        help = 'sample id to be included in report name',
        required = True
    )
    parser.add_argument(
        '-p',
        metavar = '--GENE_PANEL',
        type = str,
        help = '',
        required = False
    )
    parser.add_argument(
        '-t',
        metavar = '--THREADS',
        type = int,
        help = '',
        required = False
    )
    parser.add_argument(
        '-c',
        metavar = '--COVERAGE',
        type = str,
        help = '',
        default = '30x',
        choices = ['30x', '5x'],
        required = False
    )
    args = parser.parse_args()
    return args


def get_panel(panel):
    """
    """
    panel_genes = []
    with open(panel) as f:
        for line in f:
            panel_genes.append(line.split('\t')[0])
    panel_genes.pop(0)
    return panel_genes


def cnv_bed(cnvs, sample_id):
    """
    """
    with open(f'{sample_id}_cnv.bed', "w") as f:
        for cnv in cnvs:
            f.write(f'{cnv[0]}\t{cnv[1]}\t{cnv[2]}\t{cnv[3]}\n')


def call_classify_cnv(cpus, sample_id):
    """
    """
    infile = f'{sample_id}_cnv.bed'
    outfile = f'{sample_id}_ClassifyCNV_out'
    launch = f'ClassifyCNV.py --infile {infile} --GenomeBuild hg19 --cores {cpus} --outdir {outfile} --precise'
    system(launch)


def get_cnv_determination(sample_id):
    """
    """
    cnvs = []
    infile = f'{sample_id}_ClassifyCNV_out/Scoresheet.txt'
    with open(infile) as f:
        for line in f:
            entry = line.split('\t')
            cnvs.append((entry[1], entry[2], entry[3], entry[5]))
    clean = f'rm -rf {sample_id}_ClassifyCNV_out'
    system(clean)
    return cnvs


def process_snps(variant_list, panel, coverage):
    """
    """
    snp_list = []
    for variant in variant_list:
        if panel != None:
            snp = (
                'SNVHPOL' in variant.info.keys()
                and variant.info['gnomAD_AF'] <= 0.5
                and ( variant.info['gnomAD_AF'] >= 0.0 
                    or (variant.info['gnomAD_AF'] == -1.0
                    and variant.info['CADD'] >= 10.0
                ))
                and str(variant.info['ANN']).split('|')[3] in panel
            )
        else:
            snp = (
                'SNVHPOL' in variant.info.keys()
                and variant.info['gnomAD_AF'] <= 0.001
                and ( variant.info['gnomAD_AF'] >= 0.0 
                    or (variant.info['gnomAD_AF'] == -1.0
                    and variant.info['CADD'] >= 10.0
                ))
            )
        if snp and '30x' in coverage:
            ann = str(variant.info['ANN']).split('|')[2]
            if 'LOF' in variant.info.keys(): 
                lof = variant.info['LOF'][0]
            else: lof = '.'
            if 'NMD' in variant.info.keys():
                nmd = variant.info['NMD'][0]
            else: nmd = '.'
            gt = variant.samples['SAMPLE1'].get('GT')
            if gt != None and len(gt) > 1:
                if gt[0] == gt[1]: genotype = 'homozygous'
                elif gt[0] != gt[1]: genotype = 'heterozygous'
            else: genotype = 'None'
            adf = variant.samples['SAMPLE1'].get('ADF')
            adr = variant.samples['SAMPLE1'].get('ADR')
            fr = f'{adf[0]}:{adr[0]}, {adf[1]}:{adr[1]}'
            ann = str(variant.info['ANN']).split('|')
            gene = ann[3]
            nm = ann[6]
            codon = ann[9]
            protein = ann[10]
            revel = variant.info['REVEL']
            cadd = variant.info['CADD']
            gnomad = variant.info['gnomAD_AF']
            clinsig = variant.info['CLNSIG']
            alleleid = variant.info['ALLELEID']
            if 'PASS' in variant.filter.keys(): filter = 'PASS'
            else: filter = 'Low-QC'
            snp_list.append([
                variant.contig,
                variant.start,
                variant.stop,
                variant.ref,
                variant.alts,
                gene,
                nm,
                codon,
                protein,
                lof,
                nmd,
                genotype,
                fr,
                revel,
                cadd,
                gnomad,
                clinsig,
                alleleid,
                filter
            ])
    return snp_list


def process_svs(variant_list, panel, coverage):
    """
    """
    sv_list = []
    for variant in variant_list:
        if panel != None:
            sv = (
                'CIGAR' in variant.info.keys()
                and variant.info['gnomAD_AF'] <= 0.5
                and ( variant.info['gnomAD_AF'] >= 0.0 
                    or (variant.info['gnomAD_AF'] == -1.0
                    and variant.info['CADD'] >= 10.0
                ))
                and str(variant.info['ANN']).split('|')[3] in panel
            )
        else:
            sv = (
                'CIGAR' in variant.info.keys()
                and variant.info['gnomAD_AF'] <= 0.001
                and ( variant.info['gnomAD_AF'] >= 0.0 
                    or (variant.info['gnomAD_AF'] == -1.0
                    and variant.info['CADD'] >= 10.0
                ))
            )
        if sv and '30x' in coverage:
            ann = str(variant.info['ANN']).split('|')[2]
            if 'LOF' in variant.info.keys():
                lof = variant.info['LOF'][0]
            else: lof = '.'
            if 'NMD' in variant.info.keys():
                nmd = variant.info['NMD'][0]
            else: nmd = '.'
            gt = variant.samples['SAMPLE1'].get('GT')
            if gt != None and len(gt) > 1:
                if gt[0] == gt[1]: genotype = 'homozygous'
                elif gt[0] != gt[1]: genotype = 'heterozygous'
            else: genotype = 'None'
            adf = variant.samples['SAMPLE1'].get('ADF')
            adr = variant.samples['SAMPLE1'].get('ADR')
            fr = f'{adf[0]}:{adr[0]}, {adf[1]}:{adr[1]}'
            ann = str(variant.info['ANN']).split('|')
            gene = ann[3]
            nm = ann[6]
            codon = ann[9]
            protein = ann[10]
            cadd = variant.info['CADD']
            gnomad = variant.info['gnomAD_AF']
            clinsig = variant.info['CLNSIG']
            alleleid = variant.info['ALLELEID']
            if 'PASS' in variant.filter.keys(): filter = 'PASS'
            else: filter = 'Low-QC'
            sv_list.append([
                variant.contig,
                variant.start,
                variant.stop,
                variant.ref,
                variant.alts,
                gene,
                nm,
                codon,
                protein,
                lof,
                nmd,
                genotype,
                fr,
                cadd,
                gnomad,
                clinsig,
                alleleid,
                filter
            ])
    return sv_list
         

def process_cnvs(variant_list, panel):
    """
    """
    cnv_list = []
    for variant in variant_list:
        if panel != None:
            cnv = (
                'CNCLASS' in variant.info.keys()
                and variant.info['GENES'] in panel
            )
            cnv_multi_gene = (
                'CNCLASS' in variant.info.keys()
                and isinstance(variant.info['GENES'], tuple)
                and any(item in variant.info['GENES'] for item in panel)
            )
        else:
            cnv = ('CNCLASS' in variant.info.keys())
            cnv_multi_gene = ('SVTYPE' in variant.info.keys())
        if 'PASS' in variant.filter.keys(): filter = 'PASS'
        else: filter = 'Low-QC'
        if cnv or cnv_multi_gene:
            cnv_list.append((
                variant.contig,
                variant.start,
                variant.stop,
                variant.alts[0],
                variant.info['LENGTH'],
                variant.info['GENES'],
                variant.samples['SAMPLE1'].get('MED'),
                filter
            ))
    return cnv_list


def process_exps(variant_list, panel):
    """
    """
    exp_list = []
    for variant in variant_list:
        if panel != None:
            exp = (
                'VARID' in variant.info.keys()
                and variant.info['VARID'].split('_')[0] in panel
            )
        else:
            exp = ('VARID' in variant.info.keys())
        if exp:
            gt = variant.samples['SAMPLE1'].get('GT')
            if gt != None and len(gt) > 1:
                if gt[0] == gt[1]: genotype = 'homozygous'
                elif gt[0] != gt[1]: genotype = 'heterozygous'
            else: genotype == 'None'
            loc_coverage = variant.samples['SAMPLE1'].get('LC')
            if genotype == 'homozygous':
                if len(variant.alts) == 1:
                    allele1 = f"{variant.info['RU']}*{variant.alts[0][4:-1]}"
                    allele2 = f"{variant.info['RU']}*{variant.alts[0][4:-1]}"
            elif genotype == 'heterozygous':
                if len(variant.alts) == 2:
                    allele1 = f"{variant.info['RU']}*{variant.alts[0][4:-1]}"
                    allele2 = f"{variant.info['RU']}*{variant.alts[1][4:-1]}"
                else:
                    allele1 = f"{variant.info['RU']}*{variant.alts[0][4:-1]}"
                    allele2 = f"{variant.info['RU']}*{variant.info['REF']}"
            alleles = f"{allele1} / {allele2}"
            reference = f"{variant.info['RU']}*{variant.info['REF']}"
            if variant.info['REFREG'] == variant.info['PATHREG']: path_region = 'X'
            else: path_region = ''
            if 'PASS' in variant.filter.keys(): filter = 'PASS'
            else: filter = 'Low-QC'
            exp_list.append((
                variant.contig,
                variant.start + 1,
                variant.stop,
                reference,
                alleles,
                variant.info['VARID'].split('_')[0],
                genotype,
                loc_coverage,
                variant.info['NM'],
                variant.info['PM'],
                filter,
                path_region,
                variant.info['DISEASE'],
                variant.info['IM'],
                variant.info['SOURCE'],
                variant.info['SOURCEID']
            ))
    return exp_list


def filter_cnv(cnvs, cnv_determinations):
    """
    """
    final_cnvs = []
    for cnv in cnvs:
        for determination in cnv_determinations:
            match = (
                determination[0] in cnv[0]
                and cnv[1] == int(determination[1])
                and cnv[2] == int(determination[2])
            )
            if match:
                final_cnvs.append((
                    cnv[0],
                    cnv[1],
                    cnv[2],
                    cnv[3],
                    cnv[4],
                    cnv[5],
                    determination[3],
                    cnv[6],
                    cnv[7]
                ))
    return final_cnvs


def get_literature(panel, genes):
    """
    """
    lit = []
    with open(panel) as f:
        for line in f:
            entry = line.split('\t')
            if entry[0] in genes: 
                for pub in entry[12].split(';'):
                    if pub != '': lit.append(pub)
    lit = set(lit)
    lit_list = []
    with open('Reporting/pmc/PMC-ids.csv') as f:
        for line in f:
            pub = line.split(',') # 7 = DOI, 9 = PMID
            if pub[9] in lit: lit_list.append(f'{pub[8]}: https://doi.org/{pub[7]}')
    return lit_list


def check_interactions(final_cnvs, snp_list, sv_list, exp_list):
    """
    """
    overlaps = []
    for cnv in final_cnvs:
        cnv_dict = {
            'Chrom': cnv[0],
            'Start': cnv[1],
            'Stop': cnv[2],
            'Alt': cnv[3],
            'Length': cnv[4],
            'Genes': cnv[5],
            'Determination': cnv[6]
        }
        overlap = {
            'CNV': cnv_dict,
            'SNPs': [],
            'SVs': [],
            'EXPs': []
        }
        cnv_range = range(cnv[1], cnv[2]+1)
        for snp in snp_list:
            snp_overlap = (snp[0] == cnv[0] and snp[1] in cnv_range and snp[14] >= 10)
            if snp_overlap:
                snp_dict = snp_dict = {
                    'Chrom': snp[0],
                    'Start': snp[1],
                    'Stop': snp[2],
                    'Gene': snp[5],
                    'REVEL': round(snp[13], 2),
                    'CADD': round(snp[14], 2)
                }
                overlap['SNPs'].append(snp_dict)
        for sv in sv_list:
            sv_overlap = (sv[0] == cnv[0] and sv[1] in cnv_range and sv[13] >= 10)
            if sv_overlap:
                sv_dict = {
                    'Chrom': sv[0],
                    'Start': sv[1],
                    'Stop': sv[2],
                    'Gene': sv[5],
                    'CADD': round(sv[13], 2)
                }
                overlap['SVs'].append(sv_dict)
        for exp in exp_list:
            exp_overlap = (exp[0] == cnv[0] and exp[1] in cnv_range)
            if exp_overlap:
                exp_dict = {
                    'Chrom': exp[0],
                    'Start': exp[1],
                    'Stop' : exp[2],
                    'Gene': exp[5]
                }
                overlap['EXPs'].append(exp_dict)
        empty = (
            not overlap['SNPs']
            and not overlap['SVs']
            and not overlap['EXPs']
        )
        if not empty: overlaps.append(overlap)
    return overlaps


def make_json(panel, gene_panel, snp_list, sv_list, exp_list, final_cnvs, sample_id, interactions, low_qc = False):
    """
    """
    genes = []
    data = {}
    data['small_var'] = {
        'small_variants':[]
    }
    data['snp'] = {
        'all_snps':[],
    }
    data['sv'] = {
        'all_svs':[],
    }
    data['cnv'] = {
        'all_cnvs':[],
    }
    data['exp'] = {
        'all_expansions':[],
    }
    data['cnv_interactions'] = {
        'all_interactions': interactions
    }
    data['metadata'] = {
        'genes_in_panel': gene_panel,
        'supporting_literature':[],
        'pipeline': [
            {
                'name': 'TrimmomaticPE',
                'version': '0.39',
                'purpose': 'trim reads',
                'citation': 'https://doi.org/10.1093/bioinformatics/btu170'
            },
            {
                'name': 'BWA MEM',
                'version': '0.7.17-r1188',
                'purpose': 'paired read alignment',
                'citation': 'https://doi.org/10.1093/bioinformatics/btp324'
            },
            {
                'name': 'Samtools',
                'version': '1.10',
                'purpose': 'SAM to BAM, sorting BAM, and indexing BAM',
                'citation': 'https://pubmed.ncbi.nlm.nih.gov/19505943/'
            },
            {
                'name': 'Strelka2',
                'version': '2.9.10',
                'purpose': 'detection of SNPs and SVs',
                'citation': 'https://doi.org/10.1038/s41592-018-0051-x'
            },
            {
                'name': 'cn.MOPS',
                'version': '1.36.0',
                'purpose': 'detection of CNVs for WGS data',
                'citation': 'https://doi.org/10.1093/nar/gks003'
            },
            {
                'name': 'Manta',
                'version': '1.6.0',
                'purpose': 'detection of CNVs and stuctural variants for WGS data',
                'citation': 'https://doi.org/10.1093/bioinformatics/btv710'
            },
            {
                'name': 'ExpansionHunter',
                'version': '4.0.2',
                'purpose': 'detection of repeat expansions',
                'citation': 'https://doi.org/10.1093/bioinformatics/btz431'
            },
            {
                'name': 'ExpansionHunterDenovo',
                'version': '0.9.0',
                'purpose': 'detection of denovo repeat expansions',
                'citation': 'https://doi.org/10.1186/s13059-020-02017-z'
            },
            {
                'name': 'Gauchian',
                'version': '1.0.2',
                'purpose': 'wgs based GBA genotyper',
                'citation': 'https://doi.org/10.1101/2021.11.12.21266253'
            },
            {
                'name': 'Cyrius',
                'version': '1.1.1',
                'purpose': 'wgs based CYP2D6 genotyper',
                'citation': 'https://doi.org/10.1038/s41397-020-00205-5'
            },
            {
                'name': 'snpEff',
                'version': '5.0c',
                'purpose': 'snp annotation',
                'citation': 'https://doi.org/10.4161/fly.19695'
            },
            {
                'name': 'Bcftools',
                'version': '1.10.2',
                'purpose': 'merging and indexing vcf files',
                'citation': 'https://doi.org/10.1093/bioinformatics/btr509'
            },
            {
                'name': 'Picard',
                'version': '2.23.8',
                'purpose': 'generating bam metrics',
                'citation': 'http://broadinstitute.github.io/picard/',
            },
            {
                'name': 'FastQC',
                'version': '0.11.9',
                'purpose': 'generating fastq metrics',
                'citation': 'https://www.bioinformatics.babraham.ac.uk/projects/fastqc/'
            },
            {
                'name': 'MultiQC',
                'version': '1.9',
                'purpose': 'creating merged qc page',
                'citation': 'https://doi.org/10.1093/bioinformatics/btw354'
            },
            {
                'name': 'Nextflow',
                'version': '20.10.06',
                'purpose': 'workflow language for pipeline',
                'citation': 'https://doi.org/10.1038/nbt.3820'
            },
            {
                'name': 'Genome Build',
                'version': 'hs37d5',
                'purpose': 'reference genome',
                'citation': 'ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/reference/phase2_reference_assembly_sequence'
            },
            {
                'name': 'CADD',
                'version': 'v1.6',
                'purpose': 'variant annotation',
                'citation': 'https://cadd.gs.washington.edu/'
            },
            {
                'name': 'REVEL',
                'version': '1.0',
                'purpose': 'variant annotation',
                'citation': 'http://dx.doi.org/10.1016/j.ajhg.2016.08.016'
            },
            {
                'name': 'PMC',
                'version': '',
                'purpose': 'variant annotation',
                'citation': 'https://www.ncbi.nlm.nih.gov/pmc/'
            },
            {
                'name': 'OMIM',
                'version': '',
                'purpose': 'variant annotation',
                'citation': 'https://www.omim.org/'
            },
            {
                'name': 'gnomAD',
                'version': '2.1.1',
                'purpose': 'variant annotation',
                'citation': 'https://doi.org/10.1038/s41586-020-2308-7'
            },
            {
                'name': 'ClinVar',
                'version': 'GRcH37_2021-04-18',
                'purpose': 'variant annotation',
                'citation': 'https://doi.org/10.1093/nar/gkx1153'
            }
        ]
    }
    print('SNPs to json...')
    for snp in tqdm(snp_list):
        genes.append(snp[5])
        if snp[9] != '.': lof = snp[9].split('|')[0] + " " + snp[9].split('|')[3]
        else: lof = '.'
        if snp[10] != '.': nmd = snp[10].split('|')[0] + " " + snp[10].split('|')[3]
        else: nmd = '.'
        if snp[17] != '.': link = f"http://www.ncbi.nlm.nih.gov/clinvar/?term={snp[17]}[alleleid]"
        else: link = '.'
        snp_dict = {
            'Chrom': snp[0],
            'Start': snp[1]+1,
            'Stop': snp[2]+1,
            'Ref Allele': snp[3],
            'Alt Allele': snp[4],
            'Gene': snp[5],
            'ENSEMBL Transcript ID': snp[6],
            'Nucleotide': snp[7],
            'Protein': snp[8],
            'Loss of Function': lof,
            'Nonsense Mediated Decay Effect': nmd,
            'Genotype': snp[11],
            'F:R_ref_F:R_alt': snp[12],
            'gnomAD_AF': snp[15],
            'REVEL': snp[13],
            'CADD': snp[14],
            'ClinVar Significance': snp[16],
            'ClinVar Link': link,
            'OMIM Link': apply_omim(snp[5])
        }
        data['snp']['all_snps'].append(snp_dict)
        data['small_var']['small_variants'].append(snp_dict)
    print('SVs to json...')      
    for sv in tqdm(sv_list):
        genes.append(sv[5])
        if sv[9] != '.': lof = sv[9].split('|')[0] + " " + sv[9].split('|')[3]
        else: lof = '.'
        if sv[10] != '.': nmd = sv[10].split('|')[0] + " " + sv[10].split('|')[3]
        else: nmd = '.'
        if sv[16] != '.': link = f"http://www.ncbi.nlm.nih.gov/clinvar/?term={sv[16]}[alleleid]"
        else: link = "."
        sv_dict = {
            'Chrom': sv[0],
            'Start': sv[1]+1,
            'Stop': sv[2]+1,
            'Ref Allele': sv[3],
            'Alt Allele': sv[4],
            'Gene': sv[5],
            'ENSEMBL Transcript ID': sv[6],
            'Nucleotide': sv[7],
            'Protein': sv[8],
            'Loss of Function': lof,
            'Nonsense Mediated Decay Effect': nmd,
            'Genotype': sv[11],
            'F:R_ref_F:R_alt': sv[12],
            'gnomAD_AF': sv[14],
            'REVEL': -1.0,
            'CADD': sv[13],
            'ClinVar Significance': sv[15],
            'ClinVar Link': link,
            'OMIM Link': apply_omim(sv[5])
        }
        data['sv']['all_svs'].append(sv_dict)
        data['small_var']['small_variants'].append(sv_dict)
    print('CNVs to json...')
    for cnv in tqdm(final_cnvs):
        genes.append(cnv[5])
        cnv_dict = {
            'Chrom': cnv[0],
            'Start': cnv[1]+1,
            'Stop': cnv[2]+1,
            'Alt Allele': cnv[3],
            'Length': cnv[4],
            'Median Depth Change': cnv[7],
            'ClassifyCNV Score': cnv[6],
            'Genes': cnv[5]
        }
        data['cnv']['all_cnvs'].append(cnv_dict)
    print('EXPs to json...')
    for exp in tqdm(exp_list):
        genes.append(exp[4])
        exp_dict = {
            'Chrom': exp[0],
            'Start': exp[1]+1,
            'Stop' : exp[2]+1,
            'Ref Allele': exp[3],
            'Alt Allele' : exp[4],
            'Gene': exp[5],
            'Genotype': exp[6],
            'Locus Coverage': round(exp[7]),
            'Normal Max': exp[8],
            'Pathologic Min': exp[9],
            'Pathologic Region': exp[11],
            'Disease': exp[12],
            'Inheritance Model': exp[13],
            'Source': exp[14],
            'Source ID': exp[15]
        }
        data['exp']['all_expansions'].append(exp_dict)
    if panel != None and not low_qc:
        data['metadata']['supporting_literature'] = get_literature(panel, genes)
        with open(f'{sample_id}_{panel}_report.json', 'w') as outfile:
            dump(data, outfile, indent = 4)
    elif panel == None and not low_qc:
        data['metadata']['supporting_literature'] = None
        with open(f'{sample_id}_report.json', 'w') as outfile:
            dump(data, outfile, indent = 4)
    elif panel != None and low_qc:
        data['metadata']['supporting_literature'] = get_literature(panel, genes)
        with open(f'{sample_id}_{panel}_low-qc_report.json', 'w') as outfile:
            dump(data, outfile, indent = 4)
    else:
        data['metadata']['supporting_literature'] = None
        with open(f'{sample_id}_low-qc_report.json', 'w') as outfile:
            dump(data, outfile, indent = 4)


def apply_revel(chr, variant_list):
    """
    """
    print(f'Applying REVEL for {chr}...')
    with open(f'Reporting/revel/revel.{chr}.pkl', 'rb') as f:
        revel = pickle.load(f)
    for variant in variant_list:
        snv = ('SNVHPOL' in variant.info.keys() or 'CIGAR' in variant.info.keys())
        if variant.contig == chr and snv:
            try:
                variant.info['REVEL'] = revel[variant.contig][variant.start + 1][variant.ref][variant.alts[0]]
            except KeyError:
                continue
    del(revel)
    return variant_list


def apply_cadd(chr, variant_list):
    """
    """
    print(f'Applying CADD for {chr}...')
    for i in range(20):
        with open(f'Reporting/cadd/cadd.{chr}.{i}.pkl', 'rb') as f:
            cadd = pickle.load(f)
        for variant in variant_list:
            snv = ('SNVHPOL' in variant.info.keys() or 'CIGAR' in variant.info.keys())
            if variant.contig == chr and snv:
                try:
                    variant.info['CADD'] = cadd[variant.contig][variant.start + 1][variant.ref][variant.alts[0]]
                except KeyError:
                    continue
        del(cadd)
    return variant_list


def apply_gnomad(chr, variant_list):
    """
    """
    print(f'Applying gnomAD for {chr}...')
    with open(f'Reporting/gnomad/gnomad.{chr}.pkl', 'rb') as f:
        gnomad = pickle.load(f)
    for variant in variant_list:
        snv = ('SNVHPOL' in variant.info.keys() or 'CIGAR' in variant.info.keys())
        if variant.contig == chr and snv:
            try:
                variant.info['gnomAD_AF'] = gnomad[variant.contig][variant.start+1][variant.ref][variant.alts[0]]
            except KeyError:
                continue
    del(gnomad)
    return variant_list


def apply_clinvar(chr, variant_list):
    """
    """
    print(f'Applying ClinVar for {chr}...')
    with open(f'Reporting/clinvar/clinvar.{chr}.pkl', 'rb') as f:
        clinvar = pickle.load(f)
    for variant in variant_list:
        snv = ('SNVHPOL' in variant.info.keys() or 'CIGAR' in variant.info.keys())
        if variant.contig == chr and snv:
            try:
                variant.info['CLNSIG'] = str(clinvar[variant.contig][variant.start][variant.ref][variant.alts[0]][0])
                variant.info['ALLELEID'] = str(clinvar[variant.contig][variant.start][variant.ref][variant.alts[0]][1])
            except KeyError:
                continue
    del(clinvar)
    return variant_list


def apply_omim(gene):
    """
    """ 
    link = '.'
    with open('Reporting/omim/omim_2_gene.tsv') as omim:
        for line in omim:
            entry = line.split('\t')
            omim_id = entry[0]
            omim_gene = entry[1].strip()
            if gene == omim_gene:
                link = f'https://www.omim.org/entry/{omim_id}'
    return link


def process_variants(variant_list, panel, coverage):
    """
    """
    snp_list = process_snps(variant_list, panel, coverage)
    sv_list = process_svs(variant_list, panel, coverage)
    cnv_list = process_cnvs(variant_list, panel)
    exp_list = process_exps(variant_list, panel)
    return(snp_list, sv_list, cnv_list, exp_list)


def apply_annotations(variant_file, chr, panel, coverage):
    """
    """
    print(f'Processing {chr}...')
    vcf = VariantFile(variant_file)
    variant_list = get_variants(vcf, chr)
    variant_list = apply_clinvar(chr, variant_list)
    if chr != 'chrM':
        variant_list = apply_revel(chr, variant_list)
        variant_list = apply_gnomad(chr, variant_list)
        if chr != 'chrY':
            variant_list = apply_cadd(chr, variant_list)
    processed_variants = process_variants(variant_list, panel, coverage)
    return processed_variants


def get_variants(vcf, chr):
    """
    """
    print(f'Getting variants for {chr}...')
    variants = []
    for variant in vcf.fetch():
        if variant.contig == chr:
            variants.append(variant)
    return variants


def process_results(results):
    """
    """
    print(f'Processing results...')
    snp_list = []
    sv_list = []
    cnv_list = []
    exp_list = []
    for variant_list in results:
        for snp in variant_list[0]: snp_list.append(snp)
        for sv in variant_list[1]: sv_list.append(sv)
        for cnv in variant_list[2]: cnv_list.append(cnv)
        for exp in variant_list[3]: exp_list.append(exp)
    print(f'Length of snp_list {len(snp_list)}')
    print(f'Length of sv_list {len(sv_list)}')
    print(f'Length of cnv_list {len(cnv_list)}')
    print(f'Length of exp_list {len(exp_list)}')
    return (snp_list, sv_list, cnv_list, exp_list)
        

def thread_annotations(contigs, variant_map, panel_map, coverage_map, cpus):
    """Using multiprocessing to leverage multi-core cpus.
    """
    print('Starting multi-processing...')
    with ProcessPoolExecutor(max_workers = cpus) as executor:
        results = executor.map(apply_annotations, variant_map, contigs, panel_map, coverage_map)
    return results


def prep_vcf(variant_file, cpus):
    """
    """
    print(f'Prepping {variant_file}')
    vcf = VariantFile(variant_file)
    vcf.header.info.add("REVEL","1","Float","REVEL score for variant")
    vcf.header.info.add("CADD","1","Float","CADD score for variant")
    vcf.header.info.add("gnomAD_AF","1","Float","gnomAD allele frequency for variant")
    vcf.header.info.add("CLNSIG","1","String","ClinVar clinical significance")
    vcf.header.info.add("ALLELEID","1","String","ClinVar Allele ID")
    outfile = variant_file.split('.')[0]
    with open(outfile + "_tmp.vcf", "w") as out:
        out.write(str(vcf.header))
        for variant in vcf.fetch():
            if 'SNVHPOL' in variant.info.keys() or 'CIGAR' in variant.info.keys():
                variant.info['REVEL'] = 0.0
                variant.info['CADD'] = 0.0
                variant.info['gnomAD_AF'] = -1.0
                variant.info['CLNSIG'] = '.'
                variant.info['ALLELEID'] = '.'
                out.write('chr')
                out.write(str(variant))
            else:
                out.write('chr')
                out.write(str(variant))
    out.close()
    tabix_compress(f'{outfile}_tmp.vcf', f'{outfile}_tmp.vcf.gz')
    bcftools.index('--tbi', f'{outfile}_tmp.vcf.gz')
    return f'{outfile}_tmp.vcf.gz'


def remove_tmp_vcf(vcf):
    """
    """
    print(f'Removing {vcf}')
    command = f'rm -rf {vcf}; rm -rf {vcf}.tbi'
    system(command)


def main():
    """
    """
    contigs = (
        'chr1', 'chr2', 'chr3', 'chr4', 'chr5',
        'chr6', 'chr7', 'chr8', 'chr9', 'chr10',
        'chr11', 'chr12', 'chr13', 'chr14', 'chr15',
        'chr16', 'chr17', 'chr18', 'chr19', 'chr20',
        'chr21', 'chr22', 'chrX', 'chrY', 'chrM'
    )
    args = parse_args()
    sample_id = args.s
    panel = args.p
    if panel != None: panel = get_panel(args.p)
    cpus = args.t
    if cpus == None: cpus = 1
    vcf = prep_vcf(args.v, cpus)
    variant_map = [vcf] * len(contigs)
    panel_map = [panel] * len(contigs)
    coverage_map = [args.c] * len(contigs)
    results = thread_annotations(contigs, variant_map, panel_map, coverage_map, cpus)
    snp_list, sv_list, cnv_list, exp_list = process_results(results)
    cnv_bed(cnv_list, sample_id)
    call_classify_cnv(cpus, sample_id)
    cnv_determinations = get_cnv_determination(sample_id)
    final_cnvs = filter_cnv(cnv_list, cnv_determinations)
    # Separating the low QC and passing variants to create separate files
    passing_snp_list = []
    low_qc_snp_list = []
    passing_sv_list = []
    low_qc_sv_list = []
    passing_cnv_list = []
    low_qc_cnv_list = []
    passing_exp_list = []
    low_qc_exp_list = []
    for snp in snp_list:
        if snp[18] == 'PASS': passing_snp_list.append(snp)
        else: low_qc_snp_list.append(snp)
    for sv in sv_list:
        if sv[17] == 'PASS': passing_sv_list.append(sv)
        else: low_qc_sv_list.append(sv)
    for cnv in final_cnvs:
        if cnv[8] == 'PASS': passing_cnv_list.append(cnv)
        else: low_qc_cnv_list.append(cnv)
    for exp in exp_list:
        if exp[10] == 'PASS': passing_exp_list.append(exp)
        else: low_qc_exp_list.append(exp)
    passing_interactions = check_interactions(passing_cnv_list, passing_snp_list, passing_sv_list, passing_exp_list)
    low_qc_interactions = check_interactions(low_qc_cnv_list, low_qc_snp_list, low_qc_sv_list, low_qc_exp_list)
    make_json(args.p, panel, passing_snp_list, passing_sv_list, passing_exp_list, passing_cnv_list, sample_id, passing_interactions)
    make_json(args.p, panel, low_qc_snp_list, low_qc_sv_list, low_qc_exp_list, low_qc_cnv_list, sample_id, low_qc_interactions, low_qc = True)
    remove_tmp_vcf(vcf)


if __name__ == '__main__':
    main()
