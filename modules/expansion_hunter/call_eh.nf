#!/usr/bin/env nextflow

nextflow.enable.dsl=2

process CALL_EH {

    tag "${sample_id}"
    publishDir "${params.run_dir}/${sample_id}/ExpansionHunter", mode: 'copy'
    label 'expansion_hunter'
    label 'small_process'

    input:
    path variant_catalog
    path reference
    path ref_fai
    path ref_gzi
    tuple val(sample_id), path(bam), path(bai)

    output:
    tuple val(sample_id), file("${sample_id}_filtered_eh.vcf"), emit: eh_vcf
    tuple val(sample_id), file("${sample_id}_eh.vcf"), emit: eh_gvcf
    file "${sample_id}_eh_realigned.bam"
    file "${sample_id}_eh.json"

    shell:
    '''
    /ExpansionHunter-v4.0.2-linux_x86_64/bin/ExpansionHunter \
    --reads !{bam} \
    --reference !{reference} \
    --variant-catalog !{variant_catalog} \
    --output-prefix !{sample_id}_eh

    sed -i s/!{sample_id}_md/SAMPLE1/g !{sample_id}_eh.vcf

    grep '^#' !{sample_id}_eh.vcf > !{sample_id}_filtered_eh.vcf
    grep -v '^#' !{sample_id}_eh.vcf | \
    awk '{if ($5 !=".")print}' - >> !{sample_id}_filtered_eh.vcf
    '''
}