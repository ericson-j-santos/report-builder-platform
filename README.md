# Report Builder Platform

Plataforma reutilizável para geração declarativa e determinística de relatórios paginados (RDL), com validação fail-closed e integração opcional com Microsoft Fabric.

## Objetivo

Separar o núcleo genérico de Report Builder/Report Factory das regras de negócio dos sistemas consumidores.

O repositório deve permanecer independente de ReqSys, bancos específicos, credenciais, workspaces e ambientes particulares.

## Estado

Repositório inicializado. A primeira extração funcional será desenvolvida em branch própria e validada por CI antes de integração na main.
