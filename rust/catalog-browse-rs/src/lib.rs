#![forbid(unsafe_code)]

mod port;

use pyo3::prelude::*;

#[pymodule]
#[pyo3(name = "_native")]
fn native_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(port::category_for, m)?)?;
    m.add_function(wrap_pyfunction!(port::categories_for, m)?)?;
    m.add_function(wrap_pyfunction!(port::filtered_rows, m)?)?;
    m.add_function(wrap_pyfunction!(port::featured_rows, m)?)?;
    Ok(())
}
