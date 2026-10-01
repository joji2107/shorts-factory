# Fase 2: Docker

## Objetivo
[Crear el entorno Colima Docker]

## Por qué Colima y no Docker Desktop
[Mi ordenador tiene 8 GB de RAM asi que hay que ser cuidadosos al usar las maquinas virtuales
decidi usar colima por que es una alternativa gratuita a docker que permite decidir la cantidad de ram
que usamos. Se maneja por terminal y podemos usar los mismos comandos que en docker.]

## Conceptos
- Imagen: Es una plantilla de solo lectura con un sistema y programas ya instalados.
- Contenedor: Es una imajen en ejecución, como un mini ordenador aislado que arranamos y paramos en 
segundos.
- Por qué en Mac hay una máquina virtual: [Los contenedores necesitan el núcleo de Linux y  en mac no 
lo tenemos, por eso siempre hay una máquina virtual Linux pequeña por debajo y los contenedores corren
dentro de ella.]

## Comandos usados
| Comando | Para qué sirve |
|---------|----------------|
| `brew install` | [Homebrew es el gestor de programas de la terminal en Mac, con brew install lo que
   hacemos es decirle que programa queremos instalar] |
| `colima start` / `colima stop` | [Con estos comandos lo que hacemos es encender y apagar la maquina
   virtual que hemos creado, al apagarla deja de consumir los recursos de nuestra maquina] |
| `docker run` | [Este comando coje la una imagen que hemos instalado y la ejecuta creando un 
   contenedor] |
| `docker images` | [Con este comando vemos las imagenes que tenemos descargadas] |
| `docker ps -a` | [Lista los contenedores con -a incluye los que ya terminaron] |

## Problemas y soluciones

