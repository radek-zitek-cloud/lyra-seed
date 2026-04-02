# prime-cli-writer

CLI tool that generates the first N prime numbers and writes them to a file.

## Setup

```bash
uv sync
just check
```

## Documentation

- `docs/requirements.md`
- `docs/implementation-plan.md`

## Module Inventory

- `src/prime_cli_writer/__init__.py` - public package exports
- `src/prime_cli_writer/exceptions.py` - domain exceptions
- `src/prime_cli_writer/primes.py` - prime generation logic
- `src/prime_cli_writer/io_utils.py` - output formatting and file writing
- `src/prime_cli_writer/cli.py` - CLI parsing and orchestration

## Build Report

- **Project root**: `/home/radek/Code/lyra-seed/work/coder/prime-cli-writer`
- **Project slug**: `prime-cli-writer`
- **Package name**: `prime_cli_writer`
- **Test results**: 17 passed
- **Coverage**: 97%
- **Module inventory**:
  - `src/prime_cli_writer/__init__.py` - ~5 lines - public exports
  - `src/prime_cli_writer/exceptions.py` - ~11 lines - exception hierarchy
  - `src/prime_cli_writer/primes.py` - ~45 lines - primality checks and sequence generation
  - `src/prime_cli_writer/io_utils.py` - ~33 lines - formatting and file writing
  - `src/prime_cli_writer/cli.py` - ~63 lines - argument parsing, exit codes, orchestration
- **Known limitations**:
  - Prime generation uses simple trial division and is suitable for modest values of `N` rather than large-scale computation.
  - Runtime validation focuses on CLI input and file output errors; no special handling is added for OS-specific permission models beyond standard exceptions.
- **Run instructions**:

```bash
cd /home/radek/Code/lyra-seed/work/coder/prime-cli-writer
uv sync
just check
```
