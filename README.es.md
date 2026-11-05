# Nudge

*Read in English: [README.md](README.md)*

Un pequeño reloj de escritorio para los descansos que quieres tomarte. Lleva un temporizador independiente para cada recordatorio (beber agua, descansar, caminar, estirar, o lo que tú añadas) y, cuando toca, una animación cruza la pantalla acompañada de un sonido.

- Un temporizador **y** una frecuencia para cada recordatorio, ambos ajustables.
- Una animación y un sonido distintos por recordatorio. Puedes añadir tus propios sonidos.
- Una pausa de "Estoy en una reunión" que congela todo y te devuelve el tiempo después.
- Funciona en macOS, Windows y Linux. Escrito en Python con Tkinter, sin paquetes extra.

## Contenido

- [Instalación](#instalación)
- [Cómo usar Nudge](#cómo-usar-nudge)
- [Sonidos](#sonidos)
- [Posponer (reuniones y pausa)](#posponer-reuniones-y-pausa)
- [Si algo no funciona](#si-algo-no-funciona)
- [Qué se ha probado y qué no](#qué-se-ha-probado-y-qué-no)
- [Contribuir](#contribuir)
- [Licencia](#licencia)
- [Para desarrolladores](#para-desarrolladores)

## Instalación

No necesitas conocimientos técnicos. Descarga esta carpeta, descomprímela si hace falta y haz doble clic en el archivo de tu ordenador. Tarda aproximadamente un minuto y **nunca pide contraseña de administrador**: todo se guarda en tus propias carpetas de usuario.

| Tu ordenador | Haz doble clic en | Después encuentra Nudge aquí |
| --- | --- | --- |
| Mac | `Install on Mac.command` | Launchpad, o pulsa Comando+Espacio y escribe "Nudge" |
| Windows | `Install on Windows.bat` | Menú Inicio: pulsa la tecla Windows y escribe "Nudge" |
| Linux | `Install on Linux.sh` | El menú de aplicaciones: busca "Nudge" |

Nudge se abre solo al terminar la instalación. Si el instalador no se puede ejecutar por cualquier motivo, abre una terminal en la carpeta y escribe `python3 install.py` (en Windows: `py -3 install.py`). Hace exactamente lo mismo.

### Lo que necesitas antes: Python

Nudge necesita Python 3.8 o superior **con su librería de ventanas (Tk) en versión 8.6 o superior**. La mayoría de la gente tiene que instalarlo una vez:

- **Mac y Windows:** descarga el instalador gratuito desde [python.org/downloads](https://www.python.org/downloads/) y ejecútalo con las opciones por defecto. Incluye todo lo que Nudge necesita. Si falta Python, el instalador abre esa página por ti; instálalo y vuelve a hacer doble clic en el archivo de instalación.
- **Linux:** Python 3 suele estar, pero la librería de ventanas muchas veces no. Si falta, el instalador te muestra la línea que debes ejecutar, por ejemplo:
  - Ubuntu, Debian, Mint: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - Arch, Manjaro: `sudo pacman -S tk`

  Para el sonido en Linux también hace falta `paplay`, que viene con `pulseaudio-utils` (o `pipewire-pulse`) y ya está instalado en la mayoría de los escritorios.

> El Python que trae macOS incluye Tk 8.5, que dibuja una **ventana vacía**. El instalador lo detecta y se niega a instalar, explicando qué hacer, en lugar de dejarte con una aplicación en blanco.

### Paso a paso

**macOS**

1. Descarga y descomprime la carpeta.
2. Haz doble clic en `Install on Mac.command`. Se abre una ventana de Terminal que muestra el progreso.
3. Si macOS dice que no puede verificar el archivo: haz clic derecho sobre él, elige **Abrir** y vuelve a elegir **Abrir**. En las versiones más nuevas de macOS que no muestran el botón Abrir, ve a **Ajustes del Sistema > Privacidad y seguridad**, baja hasta el final y pulsa **Abrir igualmente** junto al aviso sobre el archivo. Solo hay que hacerlo una vez.
4. Cuando diga "Nudge is installed", pulsa cualquier tecla para cerrar la ventana. Nudge se abre.
5. A partir de ahora, ábrelo desde Launchpad o Spotlight. Nudge tiene su propio icono (un reloj con cuatro puntos de colores). El programa está en `~/Library/Application Support/Nudge` y `Nudge.app` en `~/Applications`.

**Windows**

1. Descarga y descomprime la carpeta (clic derecho sobre el zip, **Extraer todo**; no lo ejecutes desde dentro del zip).
2. Haz doble clic en `Install on Windows.bat`. Una ventana negra muestra el progreso.
3. Si aparece un cuadro azul "Windows protegió su PC", pulsa **Más información** y luego **Ejecutar de todas formas**.
4. Cuando diga "Nudge is installed", pulsa cualquier tecla. Nudge se abre.
5. A partir de ahora, pulsa la tecla Windows y escribe "Nudge". El programa está en `%LOCALAPPDATA%\Nudge` y el acceso directo en el menú Inicio. Si PowerShell está bloqueado en tu equipo, el instalador crea en su lugar un lanzador sencillo `Nudge.cmd` en la misma carpeta del menú Inicio.

**Linux**

1. Descarga y descomprime la carpeta.
2. Ejecuta `Install on Linux.sh`. Muchos gestores de archivos ofrecen **Ejecutar** o **Ejecutar en el terminal** al hacer doble clic o clic derecho. Si el tuyo lo abre en un editor de texto, abre una terminal en la carpeta y escribe `sh "Install on Linux.sh"`.
3. Cuando diga "Nudge is installed", pulsa Intro. Nudge se abre.
4. A partir de ahora, busca "Nudge" en el menú de aplicaciones. El programa está en `~/.local/share/nudge`. Si la entrada del menú no aparece enseguida, cierra sesión y vuelve a entrar.

### Actualizar

Descarga la carpeta nueva y haz doble clic en el mismo archivo de instalación. Se reemplaza el programa y **se conservan tus recordatorios y los sonidos que añadiste**. Si usabas Nudge directamente desde la carpeta descargada antes de instalarlo, la primera instalación trae esos recordatorios contigo.

### Desinstalar

Abre una terminal en la carpeta descargada y ejecuta:

```bash
python3 install.py --uninstall        # Windows: py -3 install.py --uninstall
```

Esto elimina la aplicación y su acceso, pero **conserva tus recordatorios**, por si vuelves (te dice dónde están). Añade `--remove-data` para borrarlos también:

```bash
python3 install.py --uninstall --remove-data
```

### Dónde se guardan tus datos

| Sistema | Programa y datos |
| --- | --- |
| Mac | `~/Library/Application Support/Nudge` (recordatorios en `data/state.json`, sonidos añadidos en `data/sounds/`) |
| Windows | `%LOCALAPPDATA%\Nudge` (misma estructura) |
| Linux | `~/.local/share/nudge` (misma estructura) |

Deja Nudge abierto en segundo plano: si cierras su ventana, los recordatorios dejan de sonar. Tus temporizadores se guardan, así que la próxima vez continúa donde lo dejaste.

## Cómo usar Nudge

Cada tarjeta tiene dos ajustes:

- **Frecuencia** (Frequency): cada cuánto aparece (por ejemplo, cada 40 minutos).
- **Temporizador** (Timer): cuánto dura la actividad cuando pulsas Empezar (un estiramiento de 2 minutos).

El anillo de arriba cuenta atrás hasta el próximo recordatorio. `+` y `−` ajustan una tarjeta rápidamente. **Edit** permite fijar los minutos exactos, el nombre, el color, el sonido y la animación. **Add a reminder** crea uno propio. **Preview** hace cruzar la animación por la pantalla, con su sonido, sin cambiar el calendario de ese recordatorio.

> La aplicación muestra sus textos en inglés. Los botones se nombran aquí tal como aparecen.

## Sonidos

Cada recordatorio puede tener su propio sonido. Pulsa **Edit** en una tarjeta y busca **Sound**:

- **Matches the animation** (por defecto) reproduce un sonido suave distinto para agua, descanso, paseo y estiramiento.
- **Silent** deja ese recordatorio en silencio mientras los demás siguen sonando.
- **Sonidos del sistema de Mac** como Glass, Hero o Ping aparecen en la lista en un Mac.
- **Add your own sound…** abre tus archivos. Elige cualquier sonido corto y aparecerá en la lista, listo para que cualquier recordatorio lo use. Nudge guarda su propia copia, así que sigue funcionando aunque muevas o borres el original.

Pulsa **Play**, junto a la lista, para oír un sonido antes de guardar. **Sound on / Muted**, arriba en la ventana, silencia todo de golpe.

Sonidos que puedes añadir: WAV, MP3, AIFF y M4A en Mac; WAV en Windows; WAV, OGG y FLAC en Linux. Mejor que sean cortos (unos segundos, menos de 5 MB). Si un archivo no se puede usar, Nudge explica por qué y mantiene tu elección anterior.

## Posponer (reuniones y pausa)

**In a meeting?**, abajo, congela todos los recordatorios durante 15 minutos, 30 minutos, 1 hora o 2 horas. Se reanudan solos, con el tiempo que te quedaba intacto. **Resume now** los devuelve antes.

**Pause** los congela hasta que pulses **Resume**. No se reactiva solo.

Cuando hay una alarma en pantalla:

- **Start** inicia el temporizador de ese recordatorio.
- **5 / 10 / 15 min** pospone solo ese recordatorio.
- **I'm in a meeting** pospone todo durante 30 minutos.
- **Esc** pospone el que está en pantalla 10 minutos (o termina el temporizador de la actividad si ya lo empezaste).
- **Return** inicia el temporizador.
- Si ignoras el aviso durante 5 minutos, se pospone solo 10 minutos.

El tiempo con la aplicación cerrada sigue contando, salvo que hubiera una pausa o un aplazamiento por reunión. Varios recordatorios perdidos mientras estaba cerrada (o mientras el ordenador dormía) vuelven de uno en uno en lugar de todos a la vez.

## Si algo no funciona

| Problema | Qué hacer |
| --- | --- |
| La ventana sale vacía (Mac) | El Python en uso tiene un Tk antiguo. Instala Python desde [python.org](https://www.python.org/downloads/) y vuelve a instalar Nudge. |
| La ventana no aparece | Mac: busca el icono en el Dock y haz clic. Comprueba que Nudge no esté ya abierto (te lo dice si lo está). |
| "Nudge is already running" (ya está en marcha) | Solo funciona una copia a la vez, para que no se pisen los recordatorios. Busca la ventana abierta. Si Nudge se cerró mal (un fallo, un corte de luz), el bloqueo se limpia solo y arranca con normalidad. |
| No hay sonido | Revisa el botón **Sound on / Muted**, y luego el **Sound** del recordatorio (que no sea **Silent**). Linux: instala `pulseaudio-utils` para tener `paplay`. Windows solo reproduce sonidos añadidos si son `.wav`. |
| El instalador dice que falta Python o que es muy antiguo | Instala el Python gratuito de [python.org](https://www.python.org/downloads/) y haz doble clic de nuevo en el archivo de instalación. |
| Mac o Windows avisan sobre el archivo | Mira las instrucciones paso a paso de arriba. Es una confirmación de una sola vez porque el archivo se descargó. |
| La entrada del menú de Linux no aparece | Cierra sesión y vuelve a entrar, o ejecuta `python3 ~/.local/share/nudge/main.py`. |

## Qué se ha probado y qué no

Resumen sincero, para que sepas cuánto fiarte de cada parte.

### Pruebas automáticas

`python3 tests/run_all.py` ejecuta **384 pruebas**:

| Python | Tk | Resultado |
| --- | --- | --- |
| 3.13 (Homebrew) | 9.1 | todas pasan |
| 3.9 (Python del sistema de macOS) | 8.5 | todas pasan; 2 se omiten porque necesitan Tk 8.6 o superior |

- **Cobertura de código: 94 %** de las líneas. Las que quedan sin cubrir son sobre todo manejo defensivo de errores (fallos de disco o del sistema) y la comprobación de procesos exclusiva de Windows.
- **Prueba de errores plantados:** `python3 tests/mutation_check.py` introduce 23 fallos deliberados en una copia temporal, uno a uno (por ejemplo "un recordatorio en silencio suena igualmente", "una actualización sobrescribe tus recordatorios", "Windows cierra el otro Nudge"). Las pruebas fallaron en **los 23**.
- **Prueba aleatoria:** 300 historiales aleatorios de pausa, aplazamiento y reanudación confirman que el tiempo congelado nunca se cuela en una cuenta atrás.
- **Estilo:** `pyflakes` no encuentra nada; `pycodestyle` sale limpio.

Qué cubren las pruebas automáticas: las reglas de tiempo (frecuencia, temporizador, pausa, aplazamiento por reunión, despertar del reposo), guardar y cargar (incluidos archivos dañados), añadir, editar y borrar recordatorios en la ventana real, la ventana de alarma y sus fases, elegir y reproducir sonidos, añadir sonidos propios (incluidos nombres de archivo maliciosos), los archivos que genera el instalador para los tres sistemas y el icono.

### Probado de verdad en un Mac

- La ventana principal, los diálogos de añadir y editar, las animaciones de alarma y el aviso, comprobados con capturas de pantalla.
- La instalación completa en macOS en una carpeta de usuario temporal: crear `Nudge.app`, abrirla como lo haría un doble clic (se abrió, con su propio icono en el Dock), actualizar sobre una instalación existente, desinstalar (conservando y borrando los recordatorios) y reinstalar.
- El rechazo del Tk 8.5 antiguo, con el mensaje correcto y sin instalar nada.

### No probado

| Qué | Por qué importa |
| --- | --- |
| **Todo en Windows real** (instalación, acceso directo del menú Inicio, `pythonw`, reproducción de `.wav`, la comprobación de copia en marcha) | Los archivos y comandos del instalador se construyeron y comprobaron aquí, pero PowerShell y las funciones de Windows se sustituyeron por simulaciones. |
| **Todo en Linux real** (instalación, entrada de menú, `paplay`, Tk, comportamiento de ventanas) | Igual: el archivo `.desktop` y los comandos solo se verificaron como texto. Los gestores de ventanas (y Wayland) manejan distinto las ventanas siempre-visibles y sin bordes. |
| Pulsaciones reales (Esc, Return) en la ventana de alarma | Las pruebas comprueban el foco y los manejadores de teclas, pero no pueden teclear. |
| **Oír** los sonidos | Las pruebas comprueban el comando exacto que reproduce el sonido, no el audio. No se verificó la decodificación de MP3 y M4A por el reproductor del sistema. |
| Abrir los archivos de instalación descargados con los avisos de seguridad reales de macOS y Windows | Solo están escritas las instrucciones; los avisos dependen de la versión del sistema. |
| Python 3.8 y de 3.10 a 3.12 | El código está escrito para funcionar desde la 3.8, pero solo se ejecutó con 3.9 y 3.13. |
| Varios monitores, pantallas de muy alta resolución, otras versiones de macOS o Windows | No se probó. |

Si puedes probar alguno de estos casos, cuéntanos cómo fue. Ayuda a todos.

## Contribuir

Se agradece cualquier contribución, grande o pequeña, y no hace falta ser experto:

- **Pruébalo** en un sistema que no pudimos probar (ver la tabla de arriba) y cuéntanos qué pasó, también si todo funcionó.
- **Informa de un problema** o propón una idea: abre una incidencia (issue) con lo que hiciste, lo que esperabas, lo que pasó, tu sistema y la versión de Python (`python3 --version`), y cualquier mensaje que apareciera.
- **Sugiere mejoras**: animaciones nuevas, ideas de recordatorios, textos más claros para gente no técnica, una traducción, una opción de "arrancar al iniciar sesión".
- **Envía un cambio**: haz un fork, edita, ejecuta las pruebas (abajo) y abre un pull request explicando qué y por qué.

Pautas para que todo vaya fluido:

1. Ejecuta `python3 tests/run_all.py` antes y después de tu cambio. Todo debe pasar.
2. Añade una prueba para el comportamiento nuevo o la corrección. Las pruebas de `tests/` muestran el patrón; las de ventana usan `GuiCase` en `tests/helpers.py` con un reloj simulado.
3. Mantén todo sencillo para gente no técnica: mensajes claros, sin jerga.
4. Sin dependencias externas (solo la biblioteca estándar) y compatible con Python 3.8+.
5. Para cambios en el tiempo o en el instalador, ejecuta también `python3 tests/mutation_check.py` para comprobar que las pruebas notarían un retroceso.

Las pruebas en Windows y Linux son ahora mismo la contribución más valiosa.

## Licencia

Nudge es software libre bajo la [licencia MIT](LICENSE): puedes usarlo, copiarlo, modificarlo y compartirlo, también en tu equipo o empresa, siempre que el aviso de la licencia lo acompañe. Se ofrece sin ninguna garantía. La interfaz de la aplicación está en inglés.

## Para desarrolladores

### Ejecutarlo desde la carpeta

```bash
./run.sh
```

Elige un Python con un Tk moderno. El Tk 8.5 incluido en macOS dibuja una ventana vacía, así que usa el Python de python.org o, con Homebrew:

```bash
brew install python-tk@3.13
```

`python3 main.py` a secas también cambia por sí solo a un Python adecuado. Ejecutado desde la carpeta, Nudge guarda sus datos en `data/`, junto a `main.py`.

Para ver una alarma al instante:

```bash
python3 main.py --demo
```

Las alarmas suenan a los 8, 28, 48 y 68 segundos. El modo demo usa ajustes desechables, así que tus recordatorios reales no se tocan.

```bash
python3 main.py --preview
```

reproduce al instante la animación del primer recordatorio.

### Estructura del proyecto

| Ruta | Qué es |
| --- | --- |
| `main.py` | Punto de entrada; busca un Python con un Tk moderno |
| `install.py` | Instalador por línea de comandos (los archivos de doble clic lo llaman) |
| `Install on ….command / .bat / .sh` | Lanzadores de doble clic para el instalador |
| `nudge/logic.py` | Reglas de tiempo puras (pausa, aplazamiento, despertar del reposo) |
| `nudge/app.py`, `cards.py`, `dialog.py`, `widgets.py` | Ventana principal, tarjetas, diálogo de añadir/editar |
| `nudge/overlay.py`, `sprites.py` | La ventana de alarma y sus animaciones |
| `nudge/sound.py` | Sonidos incluidos y añadidos, y su reproducción |
| `nudge/storage.py`, `models.py` | Guardar, cargar, el bloqueo de copia única, tipos de datos |
| `nudge/installer.py`, `icon.py` | Lógica del instalador y el icono dibujado |
| `tests/` | Pruebas, más `mutation_check.py` |

El icono lo dibuja `nudge/icon.py`; ejecuta `python3 -m nudge.icon` después de cambiarlo.

### Pruebas

```bash
python3 tests/run_all.py        # añade -v para listar cada prueba
```

Las pruebas de ventana abren ventanas reales (ocultas), así que ejecútalas desde una terminal normal, no desde un entorno aislado (sandbox). Se omiten solas si Tk no puede arrancar. En macOS, `run_all.py` arranca Python en un modo que evita un aviso oculto de "¿reabrir ventanas?" que podría bloquear las pruebas tras un fallo.

Para comprobar que las pruebas detectan fallos de verdad, `python3 tests/mutation_check.py` introduce dos docenas de errores deliberados, uno a uno, en una copia temporal del proyecto y confirma que las pruebas fallan en cada uno. Tarda unos minutos y nunca toca tus archivos.
