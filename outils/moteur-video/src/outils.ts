import {Easing, interpolate} from 'remotion';
import type {Effet} from './types';

export const doux = Easing.bezier(0.16, 1, 0.3, 1); // sortie très douce
export const entree = Easing.bezier(0.33, 0, 0.2, 1);

/** 0 -> 1 -> 0 : monte en `montee` s après `debut`, redescend dans les `descente` s avant `fin`. */
export const enveloppe = (t: number, debut: number, fin: number, montee = 0.4, descente = montee) => {
	if (t <= debut || t >= fin) return 0;
	const a = interpolate(t, [debut, debut + montee], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: doux,
	});
	const b = interpolate(t, [fin - descente, fin], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: entree,
	});
	return Math.min(a, b);
};

export const actif = (effets: Effet[], types: Effet['type'][], t: number) =>
	effets.some((e) => types.includes(e.type) && t >= e.debut && t < e.fin);

export const nombreFr = (v: number, decimales = 0) =>
	v.toLocaleString('fr-FR', {minimumFractionDigits: decimales, maximumFractionDigits: decimales});
