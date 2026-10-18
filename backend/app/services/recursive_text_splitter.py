import logging
import re

logger = logging.getLogger("contexthub")


DEFAULT_SEPARATORS = ["\n\n", "\n", " ", ""]


LANGUAGE_SEPARATORS: dict[str, list[str]] = {
    ".py": ["\nclass ", "\ndef ", "\n\tdef ", "\n\n", "\n", " ", ""],
    ".js": [
        "\nfunction ",
        "\nconst ",
        "\nlet ",
        "\nvar ",
        "\nclass ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\ndefault ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".jsx": [
        "\nfunction ",
        "\nconst ",
        "\nlet ",
        "\nvar ",
        "\nclass ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\ndefault ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".ts": [
        "\nenum ",
        "\ninterface ",
        "\nnamespace ",
        "\ntype ",
        "\nclass ",
        "\nfunction ",
        "\nconst ",
        "\nlet ",
        "\nvar ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\ndefault ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".tsx": [
        "\nenum ",
        "\ninterface ",
        "\nnamespace ",
        "\ntype ",
        "\nclass ",
        "\nfunction ",
        "\nconst ",
        "\nlet ",
        "\nvar ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\ndefault ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".go": [
        "\nfunc ",
        "\nvar ",
        "\nconst ",
        "\ntype ",
        "\nif ",
        "\nfor ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".rs": [
        "\nfn ",
        "\nconst ",
        "\nlet ",
        "\nif ",
        "\nwhile ",
        "\nfor ",
        "\nloop ",
        "\nmatch ",
        "\nconst ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".java": [
        "\nclass ",
        "\npublic ",
        "\nprotected ",
        "\nprivate ",
        "\nstatic ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".cpp": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".cc": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".cxx": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".hpp": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".c": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".h": [
        "\nclass ",
        "\nvoid ",
        "\nint ",
        "\nfloat ",
        "\ndouble ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".cs": [
        "\ninterface ",
        "\nenum ",
        "\nimplements ",
        "\ndelegate ",
        "\nevent ",
        "\nclass ",
        "\nabstract ",
        "\npublic ",
        "\nprotected ",
        "\nprivate ",
        "\nstatic ",
        "\nreturn ",
        "\nif ",
        "\ncontinue ",
        "\nfor ",
        "\nforeach ",
        "\nwhile ",
        "\nswitch ",
        "\nbreak ",
        "\ncase ",
        "\nelse ",
        "\ntry ",
        "\nthrow ",
        "\nfinally ",
        "\ncatch ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".rb": [
        "\ndef ",
        "\nclass ",
        "\nif ",
        "\nunless ",
        "\nwhile ",
        "\nfor ",
        "\ndo ",
        "\nbegin ",
        "\nrescue ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".php": [
        "\nfunction ",
        "\nclass ",
        "\nif ",
        "\nforeach ",
        "\nwhile ",
        "\ndo ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".swift": [
        "\nfunc ",
        "\nclass ",
        "\nstruct ",
        "\nenum ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\ndo ",
        "\nswitch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".kt": [
        "\nclass ",
        "\npublic ",
        "\nprotected ",
        "\nprivate ",
        "\ninternal ",
        "\ncompanion ",
        "\nfun ",
        "\nval ",
        "\nvar ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nwhen ",
        "\ncase ",
        "\nelse ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".scala": [
        "\nclass ",
        "\nobject ",
        "\ndef ",
        "\nval ",
        "\nvar ",
        "\nif ",
        "\nfor ",
        "\nwhile ",
        "\nmatch ",
        "\ncase ",
        "\n\n",
        "\n",
        " ",
        "",
    ],
    ".html": [
        "<body",
        "<div",
        "<p",
        "<br",
        "<li",
        "<h1",
        "<h2",
        "<h3",
        "<h4",
        "<h5",
        "<h6",
        "<span",
        "<table",
        "<tr",
        "<td",
        "<th",
        "<ul",
        "<ol",
        "<header",
        "<footer",
        "<nav",
        "<head",
        "<style",
        "<script",
        "<meta",
        "<title",
        "",
    ],
    ".md": [
        "\n#{1,6} ",
        "```\n",
        "\n\\*\\*\\*+\n",
        "\n---+\n",
        "\n___+\n",
        "\n\n",
        "\n",
        " ",
        "",
    ],
}


_REGEX_META = set(r"\.^$*+?{}[]|()\\")


def _is_regex(separator: str) -> bool:
    return any(ch in _REGEX_META for ch in separator)


def _split_text_with_regex(text: str, separator: str) -> list[str]:
    if separator:
        splits_ = re.split(f"({separator})", text)
        splits = [splits_[i] + splits_[i + 1] for i in range(1, len(splits_), 2)]
        if len(splits_) % 2 == 0:
            splits += splits_[-1:]
        splits = [splits_[0], *splits]
    else:
        splits = list(text)
    return [s for s in splits if s]


def _join_docs(docs: list[str], separator: str) -> str | None:
    text = separator.join(docs)
    text = text.strip()
    return text or None


def _merge_splits(
    splits: list[str],
    separator: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    separator_len = len(separator)
    docs: list[str] = []
    current_doc: list[str] = []
    total = 0
    for d in splits:
        len_ = len(d)
        if total + len_ + (separator_len if current_doc else 0) > chunk_size:
            if total > chunk_size:
                logger.warning(
                    "Created a chunk of size %d, which is longer than the specified %d",
                    total,
                    chunk_size,
                )
            if current_doc:
                doc = _join_docs(current_doc, separator)
                if doc is not None:
                    docs.append(doc)
                while total > chunk_overlap or (
                    total + len_ + (separator_len if current_doc else 0) > chunk_size
                    and total > 0
                ):
                    total -= len(current_doc[0]) + (
                        separator_len if len(current_doc) > 1 else 0
                    )
                    current_doc = current_doc[1:]
        current_doc.append(d)
        total += len_ + (separator_len if len(current_doc) > 1 else 0)

    doc = _join_docs(current_doc, separator)
    if doc is not None:
        docs.append(doc)
    return docs


def _split_recursive(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
    is_separator_regex: bool,
) -> list[str]:
    final_chunks: list[str] = []
    separator = separators[-1]
    new_separators: list[str] = []
    for i, s_ in enumerate(separators):
        separator_ = s_ if is_separator_regex else _regex_escape(s_)
        if not s_:
            separator = s_
            break
        if re.search(separator_, text):
            separator = s_
            new_separators = separators[i + 1 :]
            break

    separator_ = separator if is_separator_regex else _regex_escape(separator)
    splits = _split_text_with_regex(text, separator_)
    merge_separator = ""
    good_splits: list[str] = []
    for s in splits:
        if len(s) < chunk_size:
            good_splits.append(s)
        else:
            if good_splits:
                final_chunks.extend(
                    _merge_splits(good_splits, merge_separator, chunk_size, chunk_overlap)
                )
                good_splits = []
            if not new_separators:
                final_chunks.append(s)
            else:
                final_chunks.extend(
                    _split_recursive(
                        s, new_separators, chunk_size, chunk_overlap, is_separator_regex
                    )
                )

    if good_splits:
        final_chunks.extend(
            _merge_splits(good_splits, merge_separator, chunk_size, chunk_overlap)
        )

    return final_chunks


def _regex_escape(s: str) -> str:
    return re.escape(s)


def get_separators_for_language(ext: str) -> list[str]:
    return LANGUAGE_SEPARATORS.get(ext.lower(), DEFAULT_SEPARATORS)


def split_recursive_text(
    text: str,
    separators: list[str] | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    *,
    is_separator_regex: bool = False,
) -> list[str]:
    seps = separators if separators is not None else DEFAULT_SEPARATORS
    return _split_recursive(text, seps, chunk_size, chunk_overlap, is_separator_regex)


def split_recursive_text_with_indices(
    text: str,
    separators: list[str] | None = None,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    *,
    is_separator_regex: bool = False,
) -> list[tuple[str, int]]:
    chunks = split_recursive_text(
        text,
        separators=separators,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        is_separator_regex=is_separator_regex,
    )
    result: list[tuple[str, int]] = []
    index = 0
    previous_chunk_len = 0
    for chunk in chunks:
        offset = index + previous_chunk_len - chunk_overlap
        index = text.find(chunk, max(0, offset))
        result.append((chunk, index))
        previous_chunk_len = len(chunk)
    return result
