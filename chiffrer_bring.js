/* Transforme le fichier Bring! temporaire en JSON chiffré pour GitHub Pages.
   La bibliothèque SJCL utilisée est la même que celle publiée et lue par Safari 9.
*/
'use strict';
const fs = require('fs');
const path = require('path');
const sjcl = require(path.resolve('_site/sjcl.js'));
const passphrase = process.env.BRING_VIEW_KEY;
if (!passphrase || passphrase.length < 20) {
  process.stderr.write('Erreur : BRING_VIEW_KEY doit être une clé aléatoire de 20 caractères minimum.\n');
  process.exit(1);
}
const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) process.exit(1);
const data = fs.readFileSync(input, 'utf8');
const json = JSON.parse(data);
if (json.v !== 1 || !Array.isArray(json.items)) process.exit(1);
const ciphertext = sjcl.encrypt(passphrase,data,{iter:12000,ks:256,ts:128,mode:'ccm'});
fs.writeFileSync(output,ciphertext+'\n',{encoding:'utf8',mode:0o644});
// Metadonnée non sensible : date de la récupération réussie, sans articles,
// identifiant, nom de liste, détails ni mot de passe.
// Le fichier public n'est créé qu'après un chiffrement réussi.
if (typeof json.updated_at_utc === 'string' &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(json.updated_at_utc)) {
  const statusPath = path.join(path.dirname(output), 'bring-status.json');
  fs.writeFileSync(statusPath, JSON.stringify({updated_at_utc: json.updated_at_utc})+'\n',
                   {encoding:'utf8',mode:0o644});
}
process.stdout.write('Bring! : fichier chiffre cree, aucune donnee de liste affichee.\n');
