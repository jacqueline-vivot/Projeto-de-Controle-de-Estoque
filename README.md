 Sistema de Controle de Estoque
 Descrição do Projeto

O Sistema de Controle de Estoque é um software desenvolvido em Python com Tkinter e SQLite, projetado para auxiliar pequenas e médias empresas no gerenciamento de produtos, controle de entradas e saídas e geração de relatórios.

A interface é simples, intuitiva e moderna, permitindo que o usuário cadastre, visualize e atualize informações do estoque com facilidade.

 Funcionalidades
 Gestão de Produtos

Cadastro de novos produtos com nome, quantidade, preço e data de validade;

Edição e exclusão de produtos;

Exibição de todos os produtos em uma tabela dinâmica;

Busca rápida por nome.

➕ Entradas

Registro de novas entradas de produtos;

Atualização automática da quantidade em estoque.

➖ Saídas

Registro de saídas de produtos (vendas, consumo interno etc.);

Atualização automática da quantidade em estoque.

 Relatórios

Geração de relatórios de movimentações (entradas e saídas);

Exibição de totais e resumos por produto;

Identificação de produtos com baixo estoque ou validade próxima.

 Estrutura do Projeto
controle_estoque/
├── main.py                # Arquivo principal do sistema
├── database/
│   └── estoque.db         # Banco de dados SQLite
├── assets/                # Imagens e ícones (opcional)
├── README.md              # Documentação do projeto
└── requirements.txt       # Dependências do projeto

 Tecnologias Utilizadas

Python 3.10+

Tkinter — Interface gráfica

SQLite3 — Banco de dados local

Datetime — Manipulação de datas

OS / SYS — Controle de diretórios e execução


 Banco de Dados

O sistema utiliza SQLite, que não requer instalação adicional.
Tabelas principais:

produtos — Armazena informações básicas dos produtos;

entradas — Registra todas as entradas realizadas;

saidas — Registra todas as saídas realizadas.

 Possíveis Melhorias Futuras

Implementar autenticação de usuários (login e senha);

Adicionar exportação de relatórios para PDF ou Excel;

Implementar notificações automáticas de validade e baixo estoque;

Adicionar modo escuro à interface.

 Autor

Jacqueline Santos
Desenvolvido com foco em simplicidade, funcionalidade e organização.
