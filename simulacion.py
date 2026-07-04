#!/usr/bin/env python3
import asyncio, sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
# La API key se lee de la variable de entorno OPENROUTER_API_KEY
# Configúrala antes de ejecutar: export OPENROUTER_API_KEY=sk-or-v1-...
os.environ["RAPTOR_DIR"] = "/home/dani/Documentos/Raptor/raptor"
os.environ["RAPTOR_BIN"] = "/home/dani/Documentos/Raptor/raptor/bin/raptor"

from pipeline.graph import graph
from pipeline.models import AuditResult, AuditStatus, PromptInput


async def main():
    prompt = PromptInput(
        content="Creame un script de python que pida un ping a un <target IP> mandando 4 paquetes, Que me conteste si hay conexión o no?",
        target_path="/tmp/test-repo",
    )
    audit = AuditResult(prompt=prompt, status=AuditStatus.running)

    print("=" * 70)
    print("SURT IA - SIMULACIÓN COMPLETA DEL PIPELINE")
    print("=" * 70)
    print(f"\n📝 PROMPT: {prompt.content}")
    print(f"📂 TARGET RAPTOR: {prompt.target_path}")
    print()

    result = await graph.ainvoke(audit)

    if isinstance(result, dict):
        nodes = result.get("nodes", [])
        summary = result.get("summary", "")
        status = result.get("status", "")
        error = result.get("error", "")
    else:
        nodes = result.nodes
        summary = result.summary
        status = result.status
        error = result.error

    print("\n" + "=" * 70)
    print(f"ESTADO FINAL: {status}")
    print("=" * 70)

    for i, node in enumerate(nodes):
        if isinstance(node, dict):
            name = node.get("node_name", f"node_{i}")
            st = node.get("status", "")
            out = node.get("output", "")
            err = node.get("error", "")
            tok = node.get("token_usage", {})
            dur = node.get("duration_ms", 0)
        else:
            name = node.node_name
            st = node.status.value if hasattr(node.status, 'value') else node.status
            out = node.output or ""
            err = node.error or ""
            tok = node.token_usage or {}
            dur = node.duration_ms

        icon = "✅" if "completed" in str(st) else "⏳" if "running" in str(st) else "❌"
        print(f"\n{icon} [{name.upper()}] ({st})")
        print(f"   ⏱ {dur/1000:.1f}s | Tokens: {tok}")
        if err:
            print(f"   ⚠️  {err}")
        if out:
            clipped = out[:400] + "..." if len(out) > 400 else out
            print(f"   📄 {clipped}")
        print("-" * 50)

    print("\n" + "=" * 70)
    print("INFORME FINAL CONSOLIDADO")
    print("=" * 70)
    if summary:
        print(f"\n{summary}")
    elif nodes:
        last = nodes[-1]
        last_out = last.get("output", "") if isinstance(last, dict) else (last.output or "")
        print(f"\n{last_out[:2000]}")


if __name__ == "__main__":
    asyncio.run(main())
