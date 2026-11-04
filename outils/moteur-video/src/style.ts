// Charte reprise du skill « mon-style-signature » de Déborah.
import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const COULEURS = {
	creme: '#F8F6F1',
	bordeaux: '#6B1526',
	bordeauxSombre: '#3E2028',
	noir: '#181818',
	blanc: '#FFFFFF',
	lin: '#E4DCD1',
	nude: '#BBA18E',
};

export const TITRE = 'Playfair Display'; // titres, mots forts, mots-clés (souvent en italique)
export const TEXTE = 'Montserrat'; // sous-titres (Medium), étiquettes en majuscules espacées (SemiBold)

// Zone sûre en 1080x1920 : rien dans les 250 px du haut, les 400 px du bas, les 140 px de droite.
export const ZONE = {haut: 250, bas: 400, droite: 140, gauche: 60};

export const SOUS_TITRES = {taille: 70, tailleMotCle: 80, motsMax: 4};

// Volume discret des effets sonores (0 à 1)
export const VOLUME_SONS = 0.22;

const polices = [
	{family: TEXTE, file: 'montserrat-latin-500-normal.woff2', weight: '500', style: 'normal'},
	{family: TEXTE, file: 'montserrat-latin-600-normal.woff2', weight: '600', style: 'normal'},
	{family: TITRE, file: 'playfair-display-latin-600-normal.woff2', weight: '600', style: 'normal'},
	{family: TITRE, file: 'playfair-display-latin-400-italic.woff2', weight: '400', style: 'italic'},
	{family: TITRE, file: 'playfair-display-latin-600-italic.woff2', weight: '600', style: 'italic'},
] as const;

export const chargerPolices = () =>
	Promise.all(
		polices.map((p) =>
			loadFont({family: p.family, url: staticFile(`polices/${p.file}`), weight: p.weight, style: p.style}),
		),
	);

// Couleurs selon le fond : texte noir doux sur fond clair, blanc sur fond sombre.
export const teinte = (fondClair: boolean) => ({
	texte: fondClair ? COULEURS.noir : COULEURS.blanc,
	accent: fondClair ? COULEURS.bordeaux : COULEURS.creme,
	ombre: fondClair ? '0 2px 14px rgba(248,246,241,0.55)' : '0 2px 12px rgba(0,0,0,0.30)',
});
