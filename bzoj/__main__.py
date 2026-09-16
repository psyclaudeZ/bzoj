from pathlib import Path

import uvicorn


def main() -> None:
    uvicorn.run(
        "bzoj.app:app", host="127.0.0.1", port=8000,
        reload=True, reload_dirs=[str(Path(__file__).resolve().parent)],
    )


if __name__ == "__main__":
    main()
