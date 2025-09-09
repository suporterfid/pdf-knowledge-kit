"""Custom fastembed model registration."""

try:  # fastembed >=0.8 exposes ``add_custom_model``
    from fastembed import add_custom_model  # type: ignore
except Exception:  # pragma: no cover - fallback for older versions
    from fastembed import TextEmbedding
    from fastembed import PoolingType

    def add_custom_model(*, name: str, base: str, pooling: str) -> None:
        base_info = next(
            (m for m in TextEmbedding._list_supported_models() if m.model.lower() == base.lower()),
            None,
        )
        if base_info is None:
            raise ValueError(f"Base model {base} not found")
        TextEmbedding.add_custom_model(
            model=name,
            pooling=PoolingType[pooling.upper()],
            normalization=True,
            sources=base_info.sources,
            dim=base_info.dim,
            model_file=base_info.model_file,
            description=base_info.description,
            license=base_info.license,
            size_in_gb=base_info.size_in_GB,
            additional_files=base_info.additional_files,
        )

add_custom_model(
    name="paraphrase-multilingual-MiniLM-L12-v2-cls",
    base="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    pooling="cls",
)
