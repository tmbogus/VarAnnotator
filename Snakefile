# Snakefile

# Define input and output files
VCF_FILE = "input/variants.vcf"
ANNOTATED_OUTPUT = "output/annotated_variants.tsv"

# Rule to annotate variants
rule annotate_variants:
    input:
        vcf=VCF_FILE
    output:
        annotated=ANNOTATED_OUTPUT
    shell:
        """
        python scripts/annotate_variants.py {input.vcf} {output.annotated}
        """

# Rule to ensure output directory exists
rule ensure_output_dir:
    output:
        directory="output"
    shell:
        """
        mkdir -p {output}
        """

# Workflow
rule all:
    input:
        ANNOTATED_OUTPUT
