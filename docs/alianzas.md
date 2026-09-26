# Qué pedir a CONAF y SENAPRED

Notas para preparar la primera reunión. Tres cosas bloquean a PANAL hoy y
ninguna cuesta dinero: las tres ya existen, solo que no por una vía que el
código pueda alcanzar.

Están ordenadas por lo que destraban, no por lo fácil que sea pedirlas.

---

## 1. Registros de daño de febrero de 2024

**Qué:** qué estructuras se perdieron y dónde, en el incendio de Viña del Mar
y Quilpué. Idealmente por dirección o coordenada; sirve incluso agregado por
manzana.

**Por qué:** el índice de exposición urbano-forestal tiene dos mitades y solo
una está validada.

La mitad de *amenaza* —¿llegará el fuego y correrá?— valida a **3,83 veces el
azar** contra la huella satelital de ese incendio. La mitad de *consecuencia*
—¿qué tan grave si llega?— no está validada, y **una huella de quema no puede
validarla**: dice dónde ardió el monte, no dónde se perdieron casas. De 173
celdas que VIIRS vio arder, solo 9 estaban habitadas.

Los registros de daño son el único dato que cierra eso. Sin ellos, términos
como vivienda precaria o ausencia de red de agua quedan como hipótesis
razonables y nada más.

**Qué destraba:** que PANAL pueda decir "estas manzanas están en la condición
que costó vidas en 2024" en vez de "estas manzanas tienen pendiente y
combustible".

---

## 2. Catastro de Uso de Suelo y Vegetación

**Qué:** las coberturas del catastro vegetacional, a 1:50.000. Shapefile o
geodatabase sirve; un WFS sería mejor.

**Por qué:** Sentinel-2 nos da el *estado* del combustible —cuánta biomasa hay
y qué tan seca está— y eso ya funciona sin credenciales. Lo que falta es el
*tipo*, que es lo que los modelos **Kitral** dentro de Cell2Fire realmente
consumen.

Probé `sit.conaf.cl`, `ide.minagri.gob.cl` y `geoportal.cl` buscando WFS,
ArcGIS REST y GeoServer. Ninguno responde: el SIT exige navegar su propia
interfaz. No es que el dato sea reservado — es que no hay vía automatizable.

**Qué destraba:** Fase 4 completa. Sin tipo de combustible no se puede correr
C2F+K, y sin C2F+K no hay velocidad ni dirección de avance modeladas.

---

## 3. Acceso a las torres de vigía

**Qué:** que los operadores de torre puedan ingresar marcaciones, o que un
despachador las ingrese al recibirlas por radio. Y el registro de posiciones
topografiadas de las torres.

**Por qué:** es el mejor dato de detección temprana que existe y no lo tiene
nadie más. Una torre es una estación con posición conocida y observador
entrenado: un solo azimut ya es una línea de posición sin error en su origen,
y dos torres dan un fix cuyo único error es angular. Confianza T1 en segundos.

Y una marcación pesa **veinte bytes**. Sobrevive por SMS, por radio relayada,
por mensajero satelital — justo donde una foto no llega porque las antenas se
quemaron.

**La objeción que hay que resolver en la reunión:** ingresar una marcación es
trabajo adicional sobre tareas que ya tienen. Si no es casi sin fricción, no
se usa, y una red de observadores a medio adoptar es peor que ninguna porque
su silencio deja de significar algo.

Hay dos vías y conviene preguntar cuál calza con sus procedimientos:

- **En torre.** Sin transcripción, pero depende de que el vigía lo haga.
- **En central.** El despachador ingresa lo que ya recibe por radio. Cero
  carga para la torre, pero agrega un paso de transcripción.

Lo dimensioné: para que la vía central sea *peor que el satélite que ya
tenemos*, el error de azimut tendría que llegar a **5,7° a 20 km** o 3,8° a
30 km. Con confirmación por repetición en el procedimiento radial, errores de
ese tamaño deberían ser raros. Dentro de ~20 km ambas vías le ganan a GOES con
holgura, así que la decisión es de adopción, no de precisión.

Está construido para soportar las dos, con un campo que registra de cuál vino.

---

## Otras dos, más chicas

**Waze for Cities.** Es gratis y da un feed cada 2 minutos, pero está
restringido a organismos públicos sin uso comercial. PANAL es no comercial y
califica en todo salvo en ser organismo. Si CONAF o SENAPRED entran al
programa, el dato de tráfico llega por ahí — y el tráfico es lo que convierte
una evacuación en trampa mortal.

**Un punto de ingreso para zonas oficiales.** Que ellos publiquen zonas de
alerta directamente en PANAL. Esto además resuelve el límite que nos
impusimos: **PANAL no emite órdenes de evacuación.** Las alertas oficiales son
de SENAPRED vía SAE, y el rol de PANAL es mostrarlas y amplificarlas, nunca
imitar una. Con este canal eso pasa a ser un diseño en vez de una limitación.

---

## Qué ofrece PANAL a cambio

Conviene llegar con esto claro, porque la conversación no debería ser solo
pedir.

- **Código abierto, GPL-3.0, sin fines de lucro.** No vamos a cobrar por uso;
  cobrar costaría alcance y, sobre todo, la posibilidad de conectar con ellos.
- **Detección GOES cada 10 minutos** sobre todo Chile, ya funcionando, con
  latencia medida de ~1 minuto desde que cierra el barrido. En el incendio de
  Viña, GOES lo vio a las **12:10 hora local** — 2 horas 37 minutos antes de
  la primera pasada VIIRS.
- **Máscara de anomalías industriales** ya construida: 63 celdas en 12 sitios
  (El Teniente, Chuquicamata, Ventanas, Coloso), que en la ventana de 24 horas
  eran 11 de 29 detecciones. Sin eso, un despachador vería 29 incendios donde
  11 son fundiciones.
- **El replay de Viña 2024**, reproducible, a cadencia nativa de 10 minutos.
  Es lo que conviene abrir en la reunión.

---

## Lo que NO hay que prometer

El índice de exposición **no predice dónde empieza un incendio**. Predice qué
tan grave sería si llegara. Confundir eso en una reunión con gente que combate
incendios sería el error más caro posible: lo notarían de inmediato y con
razón.

Y la mitad de consecuencia todavía no está validada. Decirlo primero, antes de
que lo pregunten.
