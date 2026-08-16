# Migrazione R5c6 → R5c6a

R5c6a preserva progetti, impostazioni, runtime adottati e runtime gestiti di R5c6. Non è richiesta alcuna migrazione distruttiva.

Il componente Krea passa dal precedente placeholder basato su `turbo.safetensors` ufficiale al checkpoint Krea 2 Turbo Quanto nativamente previsto dal default corrente WanGP. I checkpoint WanGP `Krea2Turbo_quanto_bf16_int8.safetensors` e `Krea2Turbo_bf16.safetensors` già presenti vengono riutilizzati in-place e registrati come preesistenti (`ownership=reused`), quindi non vengono cancellati automaticamente dalla manutenzione. Un eventuale vecchio `turbo.safetensors` non viene mai cancellato automaticamente.

Dopo la patch: File → Gestione runtime AI → Health Check; accettare Community License/AUP solo quando si installa Krea; se il runtime base esiste già, è possibile selezionare soltanto Krea 2. Il bridge Image Gen viene sincronizzato automaticamente.
