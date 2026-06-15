from __future__ import annotations

import typer

from nl2uri.pipeline import run_full_pipeline

app = typer.Typer(help="nl2a: natural language -> URI Tree -> Domain Pack -> Agent contract")


@app.command()
def generate(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    no_llm: bool = False,
    out_dir: str = "domains",
):
    result = run_full_pipeline(prompt, no_llm=no_llm, out_dir=out_dir)
    typer.echo(str(result.domain_dir))


def main():
    app()


if __name__ == "__main__":
    main()
