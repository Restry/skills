"""Section render helpers shared across all sections."""

def escape_html(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                  .replace('"', '&quot;').replace("'", '&#39;'))

def fmt_num(n):
    return f"{n:,}"

def chips(items, warn_suffix='|warn'):
    """Render a list of strings as `<span class='pcat'>X</span>` chips.
    Items ending with `|warn` get the crimson `warn` class."""
    out = ''
    for c in items:
        if c.endswith(warn_suffix):
            out += f'<span class="pcat warn">{c[:-len(warn_suffix)]}</span>'
        else:
            out += f'<span class="pcat">{c}</span>'
    return out
