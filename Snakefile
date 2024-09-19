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
    log:
        "logs/annotate_variants.log"  # Log file to capture stdout and stderr
    shell:
        """
        python scripts/annotate_variants.py {input.vcf} {output.annotated} > {log} 2>&1
        """

# Rule to ensure output directory exists
rule ensure_output_dir:
    output:
        directory="output"
    shell:
        "mkdir -p {output}"

# Workflow entry point
rule all:
    input:
        ANNOTATED_OUTPUT
