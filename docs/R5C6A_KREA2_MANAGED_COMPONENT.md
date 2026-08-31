# R5c6a — Krea 2 Managed Component Completion

R5c6a completa il percorso Krea 2 Turbo sopra la baseline validata R5c6.

## Contratto runtime

Sprite Studio segue il default corrente WanGP `krea2_turbo` e usa `Krea2Turbo_quanto_bf16_int8.safetensors` dal repository `DeepBeepMeep/krea-2`. È il checkpoint Quanto BF16 INT8 orientato a WanGP (~13,5 GB), non il monolitico ufficiale `krea/Krea-2-Turbo/turbo.safetensors` da ~26,3 GB. Il repository ufficiale Krea resta l'autorità per Krea 2 Community License e Acceptable Use Policy.

Il bridge Image Gen gestito viene collegato automaticamente a `assets/runtime/krea2_turbo_settings_template.json`, con `model_type=krea2_turbo`, 8 step di default, guidance 0, image mode e risoluzione predefinita 1024x1024. Prompt, seed, step e risoluzione della richiesta continuano a prevalere sul template.

I checkpoint WanGP compatibili già presenti (`Krea2Turbo_quanto_bf16_int8.safetensors` oppure `Krea2Turbo_bf16.safetensors`) vengono rilevati prima di qualunque download. Il template Image Gen viene adattato al checkpoint trovato: la variante BF16 usa il proprio URL WanGP e non forza il download della variante INT8. I checkpoint preesistenti vengono registrati come `ownership=reused` e sono protetti sia dal pulsante di rimozione del modello sia dal cleanup automatico dei modelli gestiti. Il token Hugging Face è facoltativo per il checkpoint WanGP pubblico e, quando fornito, vive soltanto nell'ambiente del subprocess: non viene mai scritto nello stato runtime.

WanGP può acquisire al primo uso asset condivisi Qwen3-VL/text encoder/VAE. Il piano di storage conserva una riserva dedicata agli asset condivisi on-demand.

## Setup Windows

Il Setup espone Krea 2 Turbo come componente AI indipendente. La selezione richiede conferma esplicita di Community License + AUP e rimuove l'antico `--skip-krea2` in favore dell'installazione del componente. Se viene adottato un runtime esterno, il Setup resta non distruttivo: non installa checkpoint dentro quell'albero e mostra un avviso esplicito; un Krea già presente viene riutilizzato in-place.

## Gate di release

Il model card ufficiale Krea 2 dichiara che i deployer devono implementare misure di content filtering o un processo di revisione equivalente appropriato al caso d'uso. R5c6a registra questo requisito come gate della Windows Release Candidate: l'integrazione tecnica non equivale, da sola, all'adempimento di quell'obbligo di deployment.
