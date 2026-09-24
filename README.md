# CT7ASY Logbook — serviço experimental

Gateway HTTPS para VOACAP e DX Cluster da aplicação web. Não recebe a base de dados nem guarda contactos. Indicativo de login é enviado ao servidor DX escolhido; locators e parâmetros de previsão são enviados ao VOACAP.

Executar com um único processo Gunicorn e oito threads (sessões em memória). Ligações DX expiram após dois minutos sem consultas. Reinícios requerem que o utilizador volte a ligar. Limites de 20 sessões totais e três por IP; destinos TCP fixos; CORS apenas para a aplicação configurada. Para produção são necessários autenticação, quotas por utilizador e monitorização.

Render: criar Web Service a partir deste repositório, plano Free, build `pip install -r requirements.txt`, start `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 100 server:app`, health `/health`. Não é necessária base de dados. Definir ALLOWED_ORIGINS com a origem da aplicação (sem caminho).

O plano gratuito pode suspender o serviço por inatividade e demorar cerca de um minuto a iniciar. Destina-se a testes. Verificar os limites e condições atuais na conta antes de criar o serviço. Nenhum plano pago é autorizado automaticamente.

Depois de alojar, preencher `online-config.json` na aplicação com a propriedade `serviceUrl` a apontar para o endereço HTTPS do serviço e publicar o frontend.

Preparado em 24/09/2026. Testes locais com respostas simuladas: isolamento das sessões DX, lista de destinos permitidos, desligar e encaminhamento de previsão. Falta validar ligações reais a partir do alojamento.
