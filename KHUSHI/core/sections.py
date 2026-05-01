n = "\n"
w = " "

bold = lambda x: f"<b>{x}:</b> "
bold_ul = lambda x: f"<b><u>{x}:</u></b> "

mono = lambda x: f"<code>{x}</code>{n}"


def section(
    title: str,
    body: dict,
    indent: int = 2,
    underline: bool = False,
) -> str:
    text = (bold_ul(title) + n) if underline else bold(title) + n

    for key, value in body.items():
        if value is not None:
            text += (
                indent * w
                + bold(key)
                + (
                    (value[0] + n)
                    if isinstance(value, list) and isinstance(value[0], str)
                    else mono(value)
                )
            )
    return text
