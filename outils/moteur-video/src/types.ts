import type {Caption} from '@remotion/captions';

export type Legende = Caption & {motCle?: boolean};

type Base = {debut: number; fin: number; son?: string | false; volumeSon?: number};

export type Effet =
	| (Base & {type: 'accroche'; surtitre: string; titre: string; motFort?: string})
	| (Base & {type: 'grand_titre'; texte: string; motFort?: string})
	| (Base & {
			type: 'icone';
			icone: 'coeur' | 'check' | 'etoile' | 'goutte' | 'eclair' | 'cible';
			position?: 'droite' | 'gauche' | 'haut';
			texte?: string;
	  })
	| (Base & {
			type: 'compteur';
			valeur: number;
			decimales?: number;
			prefixe?: string;
			suffixe?: string;
			libelle?: string;
	  })
	| (Base & {type: 'carte'; contenu: 'chiffre'; valeur: number; prefixe?: string; suffixe?: string; libelle?: string})
	| (Base & {type: 'carte'; contenu: 'entonnoir'; etapes: string[]})
	| (Base & {type: 'carte'; contenu: 'chat'; question: string; reponse: string; nom?: string})
	| (Base & {type: 'carte'; contenu: 'checklist'; titre?: string; elements: string[]})
	| (Base & {type: 'zoom'; force?: number})
	| (Base & {type: 'transition'; style: 'lumiere' | 'panoramique'})
	| (Base & {type: 'fin'; nom?: string; sousTitre?: string; compte?: string; motCle?: string});

export type Props = {
	video: string;
	fps: number;
	duree: number;
	largeur: number;
	hauteur: number;
	fondClair: boolean;
	legendes: Legende[];
	parole: [number, number][];
	musique: null | {src: string; gainDb: number};
	coupes: number[];
	chapitres: {debut: number; titre: string}[];
	effets: Effet[];
	ambiance: {grain?: number; etalonnage?: boolean; chaleur?: number};
	moteurTranscription?: string;
};

export type EffetDe<T extends Effet['type']> = Extract<Effet, {type: T}>;
