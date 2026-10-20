# What happened to Stack Overflow?

How much did Stack Overflow question activity fall after ChatGPT (2022-11-30), beyond the existing downward trend? Which technologies fell most, and what happened to newcomers and answerers?

Work in progress. See [04-stackoverflow-decline.md](04-stackoverflow-decline.md) for the plan and [DATA.md](DATA.md) for data sources.

## Setup

```bash
uv sync
make check-env   # needs the Stack Exchange dump at $SOD_RAW_DIR
make test
```

Data: Stack Exchange data dump, CC BY-SA 4.0.
