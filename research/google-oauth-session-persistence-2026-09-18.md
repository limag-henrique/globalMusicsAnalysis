# Google OAuth e sessões temporárias

## Conclusão

O comportamento relatado é compatível com OAuth configurado como **Testing**:
para aplicações externas, o Google emite refresh tokens que expiram em sete dias.
Quando isso ocorre, o cliente precisa pedir consentimento novamente e a conta parece
ser desvinculada. A documentação oficial também descreve que o ADC local criado por
`gcloud auth application-default login` é uma credencial de usuário e pode exigir
reauthentication quando a política de sessão do Google Workspace expira.

Neste repositório, o fluxo do Gemini foi migrado para Vertex AI com ADC. O cliente
envia um bearer token renovado pelas credenciais do ambiente e não lê mais chaves
`GEMINI`, `GEMINI_API_KEY` ou `GOOGLE_API_KEY`. A documentação registra o script
oficial de configuração de ADC, mas ele não é executado automaticamente.

## Evidências oficiais

- [Using OAuth 2.0 to Access Google APIs](https://developers.google.com/identity/protocols/oauth2):
  refresh tokens permitem renovar access tokens, devem ser armazenados com segurança,
  e tokens de aplicações externas em estado `Testing` expiram em sete dias.
- [Manage App Audience](https://support.google.com/cloud/answer/15549945):
  autorizações de usuários de teste expiram em sete dias, inclusive refresh tokens
  obtidos com acesso offline; o estado `In production` remove essa limitação.
- [gcloud auth application-default](https://docs.cloud.google.com/sdk/gcloud/reference/auth/application-default):
  `application-default login` cria credenciais de usuário para desenvolvimento local;
  contas de serviço são o caminho alternativo para acesso da aplicação sem login de
  uma conta pessoal.
- [Gemini API in Vertex AI quickstart](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart):
  Vertex AI aceita ADC, usa o projeto/localização na URL e exige a permissão
  `roles/aiplatform.user` para chamadas do modelo.
