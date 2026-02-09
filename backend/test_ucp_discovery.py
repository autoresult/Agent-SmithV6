"""
Script para buscar manifest UCP de uma loja.

Uso:
    python test_ucp_discovery.py [store_url]

Exemplo:
    python test_ucp_discovery.py www.thenotte.com.br
"""

import json
import sys

import httpx


def fetch_manifest(store_url: str):
    """Busca e exibe manifest UCP de uma loja."""

    # Normalizar URL
    if not store_url.startswith("http"):
        store_url = f"https://{store_url}"
    store_url = store_url.rstrip("/")

    manifest_url = f"{store_url}/.well-known/ucp"

    print("\n🔍 Buscando manifest UCP...")
    print(f"   URL: {manifest_url}\n")
    print("=" * 60)

    try:
        response = httpx.get(manifest_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()

        manifest = response.json()

        # Exibe JSON formatado
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        print("=" * 60)

        # Resumo
        print("\n📋 RESUMO:")
        print(f"   Versão UCP: {manifest.get('ucp', {}).get('version', 'N/A')}")

        # Services
        services = manifest.get("ucp", {}).get("services", {})
        print(f"\n   🛠️  Services ({len(services)}):")
        for name, data in services.items():
            transports = []
            if data.get("mcp"):
                transports.append("MCP")
            if data.get("rest"):
                transports.append("REST")
            if data.get("a2a"):
                transports.append("A2A")
            print(f"      - {name} [{', '.join(transports)}]")

        # Capabilities
        capabilities = manifest.get("ucp", {}).get("capabilities", [])
        print(f"\n   ⚡ Capabilities ({len(capabilities)}):")
        for cap in capabilities:
            name = cap.get("name", "unknown")
            version = cap.get("version", "")
            print(f"      - {name} (v{version})")

        # Payment
        payment = manifest.get("payment", {})
        handlers = payment.get("handlers", [])
        if handlers:
            print(f"\n   💳 Payment Handlers ({len(handlers)}):")
            for h in handlers:
                print(f"      - {h.get('name', 'unknown')}")

        print("\n✅ Manifest válido!")

    except httpx.HTTPStatusError as e:
        print(f"❌ Erro HTTP: {e.response.status_code}")
        print(f"   {e.response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"❌ Erro de conexão: {e}")
    except json.JSONDecodeError:
        print("❌ Resposta não é JSON válido")
        print(f"   Conteúdo: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    # URL padrão ou via argumento
    store = sys.argv[1] if len(sys.argv) > 1 else "www.thenotte.com.br"
    fetch_manifest(store)
