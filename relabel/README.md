# Reetiquetado a ciegas

Las 60 etiquetas de referencia (`data/golden.jsonl`) las redactó una IA y la revisión humana no dejó registro.
Aquí se reetiqueta a mano una muestra de 15 casos, con registro, para medir:

- el acuerdo de Cris con las etiquetas de la IA (por criterio y global, con kappa de Cohen);
- el acuerdo de Cris con el evaluador compuesto sobre los mismos casos (con intervalo de Wilson).

La muestra la eligió `tools/relabel_sample.py` con la semilla 20261026, estratificada por el prefijo del id
(8 `live`, 3 `v1`, 4 `mut`) y sin mirar las etiquetas. En la hoja los casos llevan códigos ciegos (`c01`-`c15`);
la correspondencia con los ids reales está en `relabel/sample.json`.

## Reglas del registro

1. Cada fila de `labels.csv` se llena antes de ver cualquier referencia. Hasta terminar el paso 3 no abras
   `data/`, `results/`, `reports/`, `docs/`, `relabel/sample.json` ni el `RUBRIC.md` del repo (su sección
   "Ambiguous cases" trae etiquetas). La rúbrica que necesitas está dentro de la hoja.
2. `labels.csv` se commitea solo, en un commit que no toca ningún otro archivo, antes de correr la comparación.
   Así el orden queda probado en git. `tools/relabel_compare.py` se niega a correr si el último commit de
   `labels.csv` incluye otros archivos, si hay cambios sin commitear o si `labels.csv` cambió después del
   primer `RESULTS.md` commiteado.

## Pasos (unos 30 minutos)

Desde la raíz del repo, en la rama `relabel-blind`, con Python 3.11 o superior.

**1. Abre la hoja y la plantilla** (1 minuto).

```bash
open relabel/sheet.html
open -e relabel/labels.csv
```

**2. Etiqueta los 15 casos, uno por uno** (unos 25 minutos, menos de 2 por caso). Para cada código:

- en `started_at` pon la hora al empezar a leerlo (`date -Iseconds` la imprime);
- lee la petición, las llamadas con sus resultados y la respuesta final;
- pon `pass` o `fail` en `grounded`, `tool_use`, `complete` y `policy`, y en `overall`
  (según la rúbrica, `overall` es `pass` solo si los cuatro son `pass`);
- `confidence`: 1 = dudo, 2 = bastante seguro, 3 = seguro;
- `note`: una frase con el motivo de cada `fail` o de la duda (sin comas, o entre comillas);
- en `finished_at` pon la hora al terminar el caso, y pasa al siguiente.

**3. Commitea solo `labels.csv`** (1 minuto).

```bash
git commit -m "datos: etiquetas a ciegas de Cris sobre 15 casos" -- relabel/labels.csv
git show --stat HEAD
```

`git show --stat` debe listar un único archivo: `relabel/labels.csv`.

**4. Corre la comparación** (unos segundos).

```bash
python -m tools.relabel_compare
```

Si falta un valor o el commit no está solo, el script lo dice y no escribe nada. Corrige, commitea de nuevo solo
`labels.csv` y vuelve a correrlo.

**5. Lee y commitea los resultados** (3 minutos).

```bash
open relabel/RESULTS.md
git add relabel/RESULTS.md && git commit -m "docs: resultados del reetiquetado a ciegas"
```

`RESULTS.md` trae el commit de `labels.csv`, la fecha de la corrida, la semilla, el acuerdo por criterio y global
con kappa, el acuerdo con el evaluador con su intervalo de Wilson y la lista de desacuerdos. Desde aquí ya puedes
abrir las referencias y revisar cada desacuerdo; si cambias de opinión, anótalo en otro archivo, no en `labels.csv`.
