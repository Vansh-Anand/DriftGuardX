class DatasetCardGenerator:
    def __init__(self, name: str, source: str, license: str, splits: dict[str, int]):
        self.name = name
        self.source = source
        self.license = license
        self.splits = splits

    def generate_markdown(self) -> str:
        return f"""# Dataset Card for {self.name}

## Source
{self.source}

## License
{self.license} (Do not commit restricted datasets)

## Splits
""" + "\n".join(
            [f"- **{split}**: {count} samples" for split, count in self.splits.items()]
        )


def get_scifact_card() -> DatasetCardGenerator:
    return DatasetCardGenerator(
        name="SciFact (BEIR)",
        source="https://github.com/allenai/scifact",
        license="Apache-2.0",
        splits={"train": 809, "test": 300},
    )


def get_toolbench_card() -> DatasetCardGenerator:
    return DatasetCardGenerator(
        name="ToolBench",
        source="https://github.com/OpenBMB/ToolBench",
        license="Apache-2.0",
        splits={"train": 1000, "test": 200},
    )
