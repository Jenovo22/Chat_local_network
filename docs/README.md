# Portal documental de Chat LAN

Este directorio reúne las copias de lectura rápida de la documentación del
producto, sin necesidad de recorrer `chat_lan/`.

## Inicio rápido

1. Leé la [descripción funcional](descripcion-funcional.md) para conocer el
   comportamiento y los límites del prototipo.
2. Seguí la [guía de ejecución](guia-de-ejecucion.md) para iniciar el servidor
   y los clientes.
3. Consultá la [matriz de verificación](verificacion.md) antes de tomar las
   pruebas como evidencia de una capacidad.

## Documentación del producto

| Tema | Documento |
| --- | --- |
| Funcionamiento y alcance | [Descripción funcional](descripcion-funcional.md) |
| Requisitos y casos de uso | [Requisitos y casos de uso](requisitos-y-casos-de-uso.md) |
| Diseño y responsabilidades | [Arquitectura](arquitectura.md) |
| Contrato de red | [Protocolo TCP v1](protocolo.md) |
| Requisitos, pruebas y límites de evidencia | [Matriz de verificación](verificacion.md) |
| Ejecución, distribución y empaquetado | [Guía de ejecución](guia-de-ejecucion.md) |
| Alcance y pruebas del codec Go | [Migración Go](migracion-go.md) |

## Diagramas interactivos

- [Arquitectura](diagramas/arquitectura.html)
- [Recorrido de conexión, sincronización, envío y reintento](diagramas/recorrido.html)

Los JSON de candidatos y los recibos de validación de Archify están junto a cada
HTML en [`diagramas/`](diagramas/).

## Mantenimiento

Estas son copias para acceso rápido. Las fuentes canónicas siguen en
`chat_lan/docs/` y `.archify/`; al actualizar una fuente, sincronizá manualmente
su copia y los enlaces de este portal.
