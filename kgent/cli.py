from __future__ import annotations

from pathlib import Path

import click

from .agent import answer, build_client, build_default_client
from .eval import evaluate, load_cases
from .graph import build_cooccurrence_graph, build_entity_graph
from .graph_store import delete_graph, graph_path_for, save_graph
from .ingest import ingest_path
from .keystore import load_keys
from .logging_config import configure_logging
from .retriever import retrieve
from .settings import get_settings
from .store import get_store


@click.group(help="kgent: a knowledge agent over project documentation.")
def main() -> None:
    configure_logging(get_settings().log_level)


def _default_store_path() -> Path:
    return get_settings().store_path


@main.command("ingest", help="Ingest a directory and write its chunks to the store.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
def ingest_cmd(path: Path, store_path: Path | None) -> None:
    target = store_path or _default_store_path()
    docs, chunks = ingest_path(path)
    store = get_store("json", target)
    store.add(chunks)
    if hasattr(store, "set_meta"):
        store.set_meta({
            "repo_path": str(path.resolve()),
            "document_count": len(docs),
            "chunk_count": store.count(),
        })
    click.echo(f"Ingested {len(docs)} documents into {len(chunks)} chunks.")
    click.echo(f"Total in store: {store.count()} (path: {target})")


@main.command("query", help="Run a single retrieval query without calling an LLM.")
@click.argument("question", nargs=-1, required=True)
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
@click.option("-k", default=5, show_default=True, help="Number of chunks to return.")
def query_cmd(question: tuple[str, ...], store_path: Path | None, k: int) -> None:
    target = store_path or _default_store_path()
    text = " ".join(question)
    store = get_store("json", target)
    hits = retrieve(store, text, k=k)
    if not hits:
        click.echo("No matches.")
        return
    for c in hits:
        click.echo(f"\n[{c.doc_path}#{c.index}]")
        click.echo(c.text[:400])


@main.command("chat", help="Interactive chat grounded in the ingested documentation.")
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
@click.option("-k", default=5, show_default=True)
def chat_cmd(store_path: Path | None, k: int) -> None:
    target = store_path or _default_store_path()
    store = get_store("json", target)
    if store.count() == 0:
        click.echo("Store is empty. Run `kgent ingest <path>` first.")
        return
    client = build_default_client()
    click.echo(f"Connected to {type(client).__name__}. Type a question, blank line to exit.")
    while True:
        try:
            question = click.prompt(">", default="", show_default=False).strip()
        except (EOFError, click.Abort):
            click.echo()
            break
        if not question:
            break
        chunks = retrieve(store, question, k=k)
        click.echo(answer(client, question, chunks))


@main.command("eval", help="Measure retrieval quality against a labelled JSONL dataset.")
@click.argument("dataset", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
@click.option("-k", default=5, show_default=True, help="Chunks retrieved per question.")
@click.option(
    "--store-kind",
    type=click.Choice(["json", "chroma", "auto"]),
    default=None,
    help="Store backend. Defaults to KGENT_STORE / settings.",
)
@click.option("--verbose", is_flag=True, help="Show per-question results.")
def eval_cmd(
    dataset: Path,
    store_path: Path | None,
    k: int,
    store_kind: str | None,
    verbose: bool,
) -> None:
    target = store_path or _default_store_path()
    kind = store_kind or get_settings().store_kind
    store = get_store(kind, target)
    if store.count() == 0:
        raise click.ClickException("Store is empty. Run `kgent ingest <path>` first.")

    cases = load_cases(dataset)
    if not cases:
        raise click.ClickException(f"No cases found in {dataset}.")

    report = evaluate(store, cases, k=k)

    if verbose:
        for c in report.cases:
            mark = "OK  " if c.hit else "MISS"
            click.echo(
                f"[{mark}] rr={c.reciprocal_rank:.2f} recall={c.recall:.2f}  {c.question}"
            )
        click.echo("")

    click.echo(f"Store:         {kind}")
    click.echo(f"Cases:         {report.n}")
    click.echo(f"hit@{k}:         {report.hit_rate:.1%}")
    click.echo(f"MRR:           {report.mrr:.3f}")
    click.echo(f"recall@{k}:      {report.recall:.1%}")
    click.echo(f"precision@{k}:   {report.precision:.1%}")


@main.group("graph", help="Inspect or build the knowledge graph.")
def graph_group() -> None:
    pass


@graph_group.command("build", help="Build the knowledge graph from the indexed chunks.")
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
@click.option(
    "--mode",
    type=click.Choice(["cooccurrence", "entity"]),
    default=None,
    help="Defaults to KGENT_GRAPH_MODE (currently set in your settings).",
)
@click.option(
    "--provider",
    default=None,
    help="LLM provider for entity mode (defaults to your default provider).",
)
@click.option(
    "--model",
    default=None,
    help="LLM model for entity mode (defaults to KGENT_GRAPH_MODEL or your default model).",
)
def graph_build(
    store_path: Path | None,
    mode: str | None,
    provider: str | None,
    model: str | None,
) -> None:
    settings = get_settings()
    target = store_path or settings.store_path
    chosen_mode = mode or settings.graph_mode
    if chosen_mode == "off":
        raise click.ClickException(
            "KGENT_GRAPH_MODE is set to 'off'. Pass --mode cooccurrence or --mode entity."
        )

    store = get_store(settings.store_kind, target)
    if hasattr(store, "all_chunks"):
        chunks = store.all_chunks()
    else:
        chunks = getattr(store, "_chunks", []) or []
    if not chunks:
        raise click.ClickException("Store has no chunks. Run `kgent ingest <path>` first.")

    if chosen_mode == "cooccurrence":
        click.echo(f"Building co-occurrence graph from {len(chunks)} chunks...")
        graph = build_cooccurrence_graph(chunks, min_count=3)
    else:
        client_model = model or settings.graph_model or None
        disk_keys = load_keys(target)
        if provider:
            extractor = build_client(provider, client_model, api_keys=disk_keys)
        else:
            extractor = build_default_client()
            if client_model:
                extractor.model = client_model
        click.echo(
            f"Extracting entities from {len(chunks)} chunks using "
            f"{extractor.name}/{extractor.model} (this can take a while)..."
        )

        def _progress(done: int, total: int) -> None:
            if done % 10 == 0 or done == total:
                click.echo(f"  {done}/{total} chunks processed", err=True)

        graph = build_entity_graph(chunks, extractor, on_progress=_progress)

    if not graph.nodes:
        click.echo("No entities/terms could be extracted; not writing a graph.", err=True)
        delete_graph(target)
        return

    save_graph(graph, target, len(chunks), chosen_mode)
    click.echo(
        f"Built {chosen_mode} graph with {len(graph.nodes)} nodes "
        f"and {len(graph.edges)} edges -> {graph_path_for(target)}"
    )


@graph_group.command("clear", help="Delete the cached knowledge graph.")
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
def graph_clear(store_path: Path | None) -> None:
    target = store_path or get_settings().store_path
    delete_graph(target)
    click.echo(f"Removed {graph_path_for(target)} (if it existed).")


@main.command("serve", help="Run the web UI and REST API.")
@click.option("--store", "store_path", type=click.Path(path_type=Path), default=None)
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve_cmd(store_path: Path | None, host: str | None, port: int | None) -> None:
    from .server import serve

    serve(host=host, port=port, store_path=store_path)


if __name__ == "__main__":
    main()
