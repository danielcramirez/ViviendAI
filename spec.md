# Constitución de Visionario_ViviendAI

## Propósito

Transformar registros de pauta y otros canales en leads de vivienda enriquecidos,
explicables y accionables. El sistema acompaña el sueño del usuario y entrega al
asesor una ficha completa; no reemplaza la aprobación crediticia ni la asignación
formal de subsidios.

## Principios

1. Cada proyecto posee una campaña y una identidad de atribución independiente.
2. Ningún lead pierde `campaign_id`, `adset_id`, `ad_id`, `form_id`, origen o UTM.
3. La conversación pregunta qué sueña el usuario antes de interrogarlo.
4. Los cálculos financieros son determinísticos; el modelo de IA no calcula subsidios.
5. La prioridad comercial es explicable y no equivale a aprobación crediticia.
6. Se favorece el cumplimiento de la regla comercial 90/10 sin excluir ni discriminar:
   los no afiliados reciben acompañamiento y nutrición.
7. No se consulta información bancaria ni centrales de riesgo en el prototipo.
8. Toda cifra estimada muestra sus supuestos y requiere validación oficial.

## Alcance de la demo

Desde el clic contextual en una campaña de proyecto hasta la entrega del lead a
Salesforce y el seguimiento del embudo hasta la separación. Las integraciones con
Meta, SAP HANA Cloud, Salesforce y Data Lake son simuladas.

## Estados comerciales

`NUEVO → CONTACTADO → PERFILADO → CITA_AGENDADA → SEPARADO`

También existen `NUTRICIÓN` y `DESCARTADO`. La efectividad de campaña se calcula
con personas deduplicadas y separaciones, no solamente con formularios recibidos.
