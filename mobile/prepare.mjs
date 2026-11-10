import {cpSync,mkdirSync} from 'node:fs';
mkdirSync('www',{recursive:true});cpSync('../web','www',{recursive:true});
