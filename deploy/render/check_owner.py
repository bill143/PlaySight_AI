"""Diagnostics: list workspaces visible to the API key and probe billing state.

Prints owner ids/names/types only — never secret values.
"""

from __future__ import annotations

from render_api import api, session


def main() -> None:
    ses = session()
    owners = api(ses, "GET", "/owners", params={"limit": 20})
    for row in owners or []:
        owner = row.get("owner") or row
        print(
            f"owner id={owner.get('id')} name={owner.get('name')!r} "
            f"type={owner.get('type')} email={owner.get('email')}"
        )
    services = api(ses, "GET", "/services", params={"limit": 20})
    print(f"existing services: {len(services or [])}")


if __name__ == "__main__":
    main()
