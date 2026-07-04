#!/usr/bin/env python3
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from pipeline.graph import graph
from pipeline.models import AuditResult, AuditStatus, PromptInput


async def main():
    prompt = PromptInput(
        content="Creame un script de python que pida un ping a un <target IP> mandando 4 paquetes, Que me conteste si hay conexión o no?",
        use_raptor=True,
    )
    audit = AuditResult(prompt=prompt, status=AuditStatus.running)

    print("=" * 70)
    print("SURT IA - PIPELINE MULTI-AGENTE")
    print("=" * 70)
    print(f"\n📝 SOLICITUD: {prompt.content}")
    print()

    result = await graph.ainvoke(audit)
    if isinstance(result, dict):
        nodes = result.get("nodes", [])
        summary = result.get("summary", "")
    else:
        nodes = result.nodes
        summary = result.summary

    print("\n" + "=" * 70)
    print("RESULTADOS POR AGENTE")
    print("=" * 70)

    labels = {
        "validate_input": "Validación",
        "node1_gemini": "1. DeepSeek (trabajo inicial)",
        "node2_deepseek": "2. Gemini (revisión)",
        "node3_raptor_scan": "3. Claude Code (refinamiento)",
        "node4_raptor_validate": "4. Consolidación final",
    }

    for node in nodes:
        if isinstance(node, dict):
            name = node.get("node_name", "")
            st = node.get("status", "")
            out = node.get("output", "")
            dur = node.get("duration_ms", 0)
        else:
            name = node.node_name
            st = node.status.value if hasattr(node.status, 'value') else node.status
            out = node.output or ""
            dur = node.duration_ms

        icon = "✅" if "completed" in str(st) else "❌" if "failed" in str(st) else "⏳"
        label = labels.get(name, name)
        print(f"\n{icon} {label}")
        print(f"   ⏱ {dur/1000:.1f}s")
        if out:
            # Show first 500 chars
            print(f"   📄 {out[:500]}")
            if len(out) > 500:
                print(f"   ... ({len(out)} chars total)")
        print("-" * 50)

    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    if summary:
        print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(main())
