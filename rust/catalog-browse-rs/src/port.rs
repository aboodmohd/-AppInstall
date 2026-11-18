use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySlice, PyString};
use std::collections::HashSet;

const CATEGORIES: &[(&str, &str)] = &[
    (
        "Internet",
        "internet network webbrowser browser email chat instantmessaging communication social",
    ),
    (
        "Graphics",
        "graphics 2dgraphics 3dgraphics photography rastergraphics vectorgraphics imageprocessing",
    ),
    (
        "Office",
        "office wordprocessor spreadsheet presentation productivity finance publishing",
    ),
    (
        "Development",
        "development ide debugger programming texteditor revisioncontrol building",
    ),
    (
        "Games",
        "game games actiongame arcadegame boardgame cardgame logicgame puzzlegame roleplaying simulation strategygame",
    ),
    (
        "Multimedia",
        "audiovideo multimedia audio video music player recorder midi audiovideoediting",
    ),
    ("Education", "education teaching learning languages"),
    (
        "Science",
        "science math physics chemistry biology astronomy geography",
    ),
    (
        "Utilities",
        "utility utilities accessories archiving compression calculator filemanager filetools",
    ),
    (
        "System",
        "system settings monitor filesystem security hardware",
    ),
    ("Other", ""),
];

fn category_for_folded(value: &str) -> &'static str {
    for token in value.split([',', ';', '/', '|']) {
        let key: String = token
            .chars()
            .filter(|c| !c.is_whitespace() && !matches!(c, '\u{1c}'..='\u{1f}' | '_' | '-'))
            .collect();
        if let Some((name, _)) = CATEGORIES
            .iter()
            .find(|(_, aliases)| aliases.split_ascii_whitespace().any(|alias| alias == key))
        {
            return name;
        }
    }
    "Other"
}

#[pyfunction]
pub fn category_for(row: &Bound<'_, PyAny>) -> PyResult<&'static str> {
    if !row.is_instance_of::<PyDict>() {
        return Ok("Other");
    }
    let value = row.call_method1("get", ("category", ""))?;
    if !value.is_instance_of::<PyString>() {
        return Ok("Other");
    }
    // Python slices by code points and uses its own Unicode casefold table.
    let prefix = value.get_item(PySlice::new(row.py(), 0, 140, 1))?;
    let folded = prefix.call_method0("casefold")?;
    Ok(category_for_folded(
        &folded.cast::<PyString>()?.to_string_lossy(),
    ))
}

#[pyfunction]
pub fn categories_for(rows: &Bound<'_, PyAny>) -> PyResult<Vec<&'static str>> {
    let mut found = HashSet::new();
    for row in rows.try_iter()? {
        found.insert(category_for(&row?)?);
    }
    Ok(std::iter::once("All")
        .chain(
            CATEGORIES
                .iter()
                .map(|(name, _)| *name)
                .filter(|name| found.contains(name)),
        )
        .collect())
}

#[pyfunction]
pub fn filtered_rows<'py>(
    rows: &Bound<'py, PyAny>,
    selected: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyList>> {
    let py = rows.py();
    if selected.eq("All")? {
        return Ok(py.get_type::<PyList>().call1((rows,))?.cast_into()?);
    }
    let result = PyList::empty(py);
    for &(name, _) in CATEGORIES {
        if selected.eq(name)? {
            for row in rows.try_iter()? {
                let row = row?;
                if selected.eq(category_for(&row)?)? {
                    result.append(row)?;
                }
            }
            break;
        }
    }
    Ok(result)
}

#[pyfunction]
pub fn featured_rows<'py>(
    rows: &Bound<'py, PyAny>,
    source: &Bound<'py, PyAny>,
    query: Bound<'py, PyAny>,
    limit: Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyList>> {
    let py = rows.py();
    let result = PyList::empty(py);
    if source.ne("Flatpak")? || query.str()?.call_method0("strip")?.is_truthy()? || limit.le(0)? {
        return Ok(result);
    }
    let seen = pyo3::types::PySet::empty(py)?;
    for row in rows.try_iter()? {
        let row = row?;
        if !row.is_instance_of::<PyDict>()
            || row
                .call_method1("get", ("source", "Flatpak"))?
                .ne("Flatpak")?
        {
            continue;
        }
        let key = row.call_method1("get", ("providerKey",))?;
        if !key.is_instance_of::<PyString>()
            || !key.call_method1("startswith", ("flatpak:",))?.is_truthy()?
            || seen.contains(&key)?
        {
            continue;
        }
        seen.add(key)?;
        result.append(row)?;
        let Ok(cap) = 6_i32.into_pyobject(py);
        let cap = cap.into_any();
        let cap = if limit.lt(&cap)? { &limit } else { &cap };
        let Ok(length) = result.len().into_pyobject(py);
        if length.ge(cap)? {
            break;
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::category_for_folded;

    #[test]
    fn first_matching_alias_wins() {
        assert_eq!(category_for_folded("unknown|2d_graphics,game"), "Graphics");
    }

    #[test]
    fn matches_python_whitespace_and_unknown_categories() {
        assert_eq!(category_for_folded("\u{1c}web\u{a0}browser"), "Internet");
        assert_eq!(category_for_folded("fedora 44"), "Other");
    }
}
