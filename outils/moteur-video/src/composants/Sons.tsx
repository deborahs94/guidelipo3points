import {Audio} from '@remotion/media';
import React from 'react';
import {Sequence, interpolate, staticFile, useVideoConfig} from 'remotion';
import {VOLUME_SONS} from '../style';
import type {Effet, Props} from '../types';

type Son = {nom: string; a: number; volume: number};

const SON_PAR_DEFAUT: Record<Effet['type'], string[]> = {
	accroche: ['montee'],
	grand_titre: ['impact'],
	icone: ['pop', 'scintillement'],
	compteur: ['montee'],
	carte: ['whoosh'],
	zoom: ['whoosh'],
	transition: ['scintillement'],
	fin: ['scintillement'],
};

/** Un effet sonore discret calé sur chaque animation. */
const listeSons = (effets: Effet[]): Son[] => {
	const sons: Son[] = [];
	for (const e of effets) {
		if (e.son === false) continue;
		const v = e.volumeSon ?? VOLUME_SONS;
		let noms = e.son ? [e.son] : SON_PAR_DEFAUT[e.type];
		if (e.type === 'transition' && e.style === 'panoramique' && !e.son) noms = ['whoosh'];
		const a = e.type === 'transition' ? e.debut - (e.style === 'lumiere' ? 0.3 : 0.2) : e.debut;
		noms.forEach((nom, i) => sons.push({nom, a: a + i * 0.08, volume: nom === 'scintillement' ? v * 0.7 : v}));
		if (e.type === 'carte') {
			sons.push({nom: 'whoosh', a: e.fin - 0.45, volume: v * 0.8}); // retour plein écran
			if (e.contenu === 'chat') {
				const n = e.question.length;
				for (let k = 0; k < n; k += 3) sons.push({nom: 'tic', a: e.debut + 0.55 + k / 26, volume: v * 0.45});
				sons.push({nom: 'pop', a: e.debut + 0.55 + n / 26 + 0.7, volume: v * 0.8});
			}
			if (e.contenu === 'checklist') e.elements.forEach((_, i) => sons.push({nom: 'pop', a: e.debut + 0.85 + i * 0.45, volume: v * 0.7}));
			if (e.contenu === 'entonnoir') e.etapes.forEach((_, i) => sons.push({nom: 'tic', a: e.debut + 0.5 + i * 0.28, volume: v * 0.8}));
			if (e.contenu === 'chiffre') sons.push({nom: 'montee', a: e.debut + 0.4, volume: v});
		}
	}
	return sons.filter((s) => s.a >= 0);
};

export const Sons: React.FC<{effets: Effet[]}> = ({effets}) => {
	const {fps} = useVideoConfig();
	return (
		<>
			{listeSons(effets).map((s, i) => (
				<Sequence key={i} from={Math.round(s.a * fps)} durationInFrames={Math.round(1.2 * fps)} layout="none" name={`Son ${s.nom}`}>
					<Audio src={staticFile(`sons/${s.nom}.wav`)} volume={s.volume} />
				</Sequence>
			))}
		</>
	);
};

/** Musique facultative : 20 dB sous la voix pendant que je parle, remonte un peu (+6 dB) dans les silences. */
export const Musique: React.FC<{p: Props}> = ({p}) => {
	const {fps} = useVideoConfig();
	if (!p.musique) return null;
	const base = Math.pow(10, p.musique.gainDb / 20);
	const volume = (f: number) => {
		const t = f / fps;
		let distance = Infinity; // distance (s) à la parole la plus proche
		for (const [a, b] of p.parole) {
			if (t >= a && t <= b) distance = 0;
			else distance = Math.min(distance, Math.abs(t - a), Math.abs(t - b));
		}
		const remontee = interpolate(distance, [0.15, 0.6], [1, 2], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const fondus = Math.min(
			interpolate(t, [0, 1], [0, 1], {extrapolateRight: 'clamp'}),
			interpolate(t, [p.duree - 1.5, p.duree], [1, 0], {extrapolateLeft: 'clamp'}),
		);
		return Math.min(1, base * remontee * fondus);
	};
	return <Audio src={staticFile(p.musique.src)} loop volume={volume} name="Musique" />;
};
