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
azar** contra la huella satelital de ese incendio: 44 de las 115 celdas
habitadas de la zona de interfaz caen en su decil superior, donde el azar
daría 12.

La mitad de *consecuencia* —¿qué tan grave si llega?— **no está validada, y
lleva el peso mayor**. Egreso 0,30, precariedad 0,25, vulnerabilidad 0,25,
sin red de agua 0,20: el 100% del peso del daño y el 0% de la evidencia.

Y una huella de quema no puede cerrarla: dice dónde ardió el monte, no dónde
se perdieron casas. De 173 celdas que VIIRS vio arder, **solo 9 estaban
habitadas**.

Los registros de daño son el único dato que cierra eso. Sin ellos, el índice
puede decir "estas celdas tienen pendiente, combustible y pasajes ciegos",
pero no "estas celdas están en la condición que costó vidas".

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

## Antes de nada: ya tienen un visor

**SENAPRED publicó el [Visor Chile Preparado](https://www.visorchilepreparado.cl)**
— amenaza volcánica, incendio forestal y tsunami, por dirección, orientado a
familias y comunidad organizada. Entrar a la reunión sin haberlo visto sería
el peor arranque posible.

No es competencia, y conviene poder explicar por qué en una frase: **responde
una pregunta distinta**.

Su capa de incendio es `Densidad de Incendios Forestales 2020-2024
(Inc./Km²)` — **recurrencia histórica**, 9.400 polígonos. Dice dónde ha
ardido antes. PANAL dice, con el combustible y el terreno de esta temporada
seca, dónde correría un incendio si llegara. Correlación de rangos entre
ambas: **0,145**. Miden cosas diferentes, y eso es exactamente el argumento.

### Tres huecos concretos en su visor que PANAL llena

1. **No tiene detección en vivo.** Es un mapa estático. Su propia hoja de ruta
   pública dice que las versiones futuras sumarán *"alertas en tiempo real y
   notificaciones automáticas"*. Eso es lo que PANAL ya tiene corriendo:
   GOES cada 10 minutos, más VIIRS.

2. **Incendio forestal no tiene vías de evacuación ni puntos de encuentro.**
   Tsunami sí. Volcán sí. Incendio no. Es justo el trabajo de egreso de
   Fase 2 — y es la capa que, si alguien la mira, es donde murió la gente.

3. **Su capa de incendio es retrospectiva.** Un cerro que nunca se quemó pero
   acumuló combustible cinco temporadas seguidas no aparece. PANAL lo ve
   porque mide el estado actual, no el historial.

### Sus capas son públicas y deberíamos estar usándolas

El visor es una app ArcGIS y sus 22 capas viven en una organización pública.
Dos importan de inmediato:

- **`Amenaza_por_Incendio_Forestal_2024`** — recurrencia. Mi roadmap listaba
  "historial de incendios" como insumo de Fase 2 y nunca lo construí. Está
  acá, listo.
- **`Servicios_2024` capa BOMBEROS** — ubicación de cuarteles. Tiempo de
  respuesta es un término de consecuencia que no tenemos.

Pedir permiso explícito para consumirlas, aunque sean públicas. Es barato
para ellos y cambia la conversación de "les pedimos datos" a "estamos
construyendo sobre lo suyo".

### Lo que NO hay que decir

Medí su capa contra la nuestra en el mismo test: recurrencia SENAPRED da
2,17× el azar, PANAL 3,83×. **Eso no se menciona.**

Tres razones. Su capa cubre 2020-2024, así que probablemente *incluye* el
incendio contra el que testeé — su 2,17× es un piso, no un techo. Combinarlas
ingenuamente da 2,78×, peor que PANAL sola, así que tampoco es que se sumen.
Y sobre todo: llegar a decirle a un organismo público que su herramienta
puntúa peor que la nuestra es la forma más rápida de no tener una segunda
reunión.

El marco correcto es el de arriba: **preguntas distintas, y la suya es un
insumo que deberíamos estar usando.**

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
- **Mapa de exposición urbano-forestal de la Región de Valparaíso**, con las
  cuatro capas: Censo 2024 a nivel manzana, pendiente Copernicus 30 m,
  combustible Sentinel-2 y capacidad de salida desde OpenStreetMap.

  Resultado concreto para llevar: **62 celdas donde amenaza y consecuencia
  están ambas en el decil superior — 5.518 viviendas, 12.555 personas**,
  concentradas en los cerros de Valparaíso. Con egreso conocido en 60 de las
  62, así que el hueco de mapeo no afecta el resultado.

  La cobertura de OpenStreetMap sobre lo habitado es **95,7% ponderada por
  población** (95,2% entre celdas con 10 o más viviendas, 86,1% de esas en
  pendientes sobre 25°). Lo medimos antes de confiar en el número.

---

## Lo que NO hay que prometer

El índice de exposición **no predice dónde empieza un incendio**. Predice qué
tan grave sería si llegara. Confundir eso en una reunión con gente que combate
incendios sería el error más caro posible: lo notarían de inmediato y con
razón.

Y la mitad de consecuencia todavía no está validada. **Decirlo primero, antes
de que lo pregunten** — es además el puente natural al pedido número uno.

Tampoco prometer que el índice reemplaza el criterio de nadie. Rankea 44.106
celdas para que alguien que conoce el terreno mire 62 en vez de todas. Eso es
todo lo que hace, y es suficiente.
