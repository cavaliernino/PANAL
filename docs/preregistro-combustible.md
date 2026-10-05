# Pre-registro: tipo de combustible con ESA WorldCover

**Escrito el 2026-10-05, antes de escribir el código y antes de construir las
huellas de los incendios reservados.** Si este archivo cambia después de esa
fecha, `git log` lo muestra; eso es lo que lo hace un pre-registro.

## Por qué

La mitad de amenaza del índice (`engine/panal_engine/wui.py`) funciona en dos
de cuatro incendios (`ingest/scripts/validate_wui.py`):

| incendio | lift |
|---|---|
| Valparaíso, Rocuant–San Roque, dic-2019 | 2,77× |
| Viña del Mar, Nueva Esperanza, dic-2022 | 0,67× |
| Viña del Mar–Quilpué, feb-2024 | 3,91× |
| Ñuble–Biobío, ene-2026 | 1,23× |

Falla en población densa (las casas son el combustible) y en plantaciones (el
término de sequedad lee el dosel verde como húmedo). Las dos fallas son de
**tipo** de combustible, que Sentinel-2 no da. CONAF lo tiene en el Catastro;
mientras llega, se prueba ESA WorldCover como sustituto.

El riesgo es obvio: con cuatro incendios a la vista, cualquier regla se puede
torcer hasta que los cuatro den bien. Por eso las reglas, la métrica y el
criterio quedan fijos acá, y la decisión se toma con incendios que nadie ha
mirado.

## Datos

- **Cobertura:** ESA WorldCover **2020** v100, 10 m. Es anterior a todos los
  incendios salvo Rocuant 2019, donde describe el paisaje de después; se
  reporta igual y se anota.
- **Por celda:** la fracción de cada clase dentro de la celda.
- **NDVI y NDMI:** los de siempre, del build con combustible anterior al
  incendio.

## Reglas, fijas

Con `b` = biomasa y `s` = sequedad, las rampas de `fuel.fuel_factor`:

- **R0, la actual:** `combustible = b · s`.
- **R1, árboles sin castigo de sequedad:**
  `combustible = f_árboles · b + f_otra_vegetación · b · s`, donde
  `f_otra_vegetación` es matorral + pradera + cultivo + humedal herbáceo.
  Construido, suelo desnudo, agua y nieve aportan 0. La idea: un dosel verde
  de pino o eucalipto arde en una ola de calor aunque el NDMI diga húmedo.
- **R2, R1 más las casas precarias como combustible:**
  `combustible = R1 + f_construido · frac_precario`. La idea: en un
  campamento, la madera y las mediaguas *son* el combustible. `frac_precario`
  ya existe (Censo 2024) y no lleva peso nuevo.

Ninguna tiene parámetros libres nuevos. La amenaza sigue siendo
`sqrt(combustible · pendiente)` con la puerta de presencia.

## Métrica

La del protocolo: lift del decil superior en la interfaz de 3 anillos, con
combustible anterior al incendio (`validate_wui.py --event`). Resumen por
conjunto: **media geométrica** de los lifts.

## Incendios

- **Desarrollo, ya vistos:** los cuatro de arriba. Se reportan, no deciden.
- **Reservados, sin construir todavía:**
  - `quilpue2021` — Quilpué, Lago Peñuelas y Las Palmas, 15 de enero de 2021,
    Región de Valparaíso. Matorral; 2.630 ha.
  - `biobio2023` — Santa Ana–Santa Juana–Nacimiento y Ñuble, 2 al 6 de
    febrero de 2023. Plantaciones; 64.500 ha, 873 viviendas en Biobío.

Los reservados se evalúan **una vez**, con las tres reglas ya escritas, y el
resultado se publica sea cual sea.

## Criterio

Una regla reemplaza a R0 solo si, **en los reservados**:

1. su media geométrica de lift es mayor que la de R0, y
2. no baja de 1,5× ningún incendio que con R0 estaba sobre 1,5×.

Si ninguna cumple, R0 se queda y el resultado se publica igual: sería
evidencia de que WorldCover no basta y de que el Catastro de CONAF hace falta
de verdad.

---

## Resultado — 2026-10-05

Las reglas se commitearon (`7f22406`) antes de evaluar los reservados, y los
reservados se evaluaron una sola vez.

**Desarrollo** (no decide):

| incendio | R0 | R1 | R2 |
|---|---|---|---|
| Rocuant 2019 | 2,77 | 1,49 | 1,49 |
| Viña 2022 | 0,67 | 0,57 | 0,67 |
| Viña 2024 | 3,91 | 3,74 | 3,74 |
| Ñuble–Biobío 2026 | 1,23 | 1,69 | 1,69 |
| media geométrica | 1,73 | 1,52 | 1,58 |

**Reservados** (deciden):

| incendio | celdas de interfaz | R0 | R1 | R2 |
|---|---|---|---|---|
| Quilpué 2021 | 44 | 0,00 | 0,00 | 0,00 |
| Biobío–Ñuble 2023 | 6.890 | 1,49 | 1,26 | 1,26 |

**Decisión: R0 se queda.** Ni R1 ni R2 superan a R0 en los reservados. R1
hace lo que se esperaba en plantaciones solo en uno de los dos incendios de
Biobío, y en el otro empeora; además diluye el combustible en celdas urbanas
mixtas. WorldCover no basta como sustituto del tipo de combustible.

**Y lo que esto dice del índice, más allá de las reglas:** contra seis
incendios, la amenaza supera 1,5× en dos (Valparaíso 2019 y 2024), queda
débil en dos (Biobío 2023 y 2026) y sin habilidad en dos (Viña 2022 y
Quilpué 2021). El cero de Quilpué es instructivo: el fuego corrió por la
reserva Lago Peñuelas, y la interfaz fue el borde plano y suburbano de
Quilpué (5° contra 10° de la región), donde el índice dice que un incendio
no correría, y donde se quemaron unas siete casas. Estar cerca de una huella
no es sufrir daño. La prueba que de verdad sirve sigue siendo la que
requiere los registros de daño de CONAF y SENAPRED.
