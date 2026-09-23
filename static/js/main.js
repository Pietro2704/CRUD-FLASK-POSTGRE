// tables.html
function addColumn() {
    const container = document.getElementById('columns');
    const div = document.createElement('div');
    div.className = 'column-row d-flex flex-wrap gap-2 align-items-center';
    div.innerHTML = `
      <input type="text" name="col_name" class="form-control" style="max-width: 220px"
             placeholder="nome da coluna" pattern="[A-Za-z_][A-Za-z0-9_]*" required>
      <select name="col_type" class="form-select" style="max-width: 160px">
        ${typeOptions.map(t => `<option value="${t}">${t}</option>`).join('')}
      </select>
      <select name="col_nullable" class="form-select" style="max-width: 200px">
        <option value="yes">Permite nulo</option>
        <option value="no">Obrigatório (NOT NULL)</option>
      </select>
      <button type="button" class="btn btn-outline-danger btn-sm" onclick="this.closest('.column-row').remove()">
        <i class="bi bi-trash"></i>
      </button>
    `;
    container.appendChild(div);
}