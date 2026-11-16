import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux, enveloppe, nombreFr} from '../outils';
import {COULEURS, TEXTE, TITRE} from '../style';
import type {EffetDe} from '../types';

/** Chiffre qui défile jusqu'à sa valeur (réutilisé dans la carte « chiffre »). */
export const Chiffre: React.FC<{
	valeur: number;
	decimales?: number;
	prefixe?: string;
	suffixe?: string;
	libelle?: string;
	t: number;
	duree: number;
	couleur: string;
	couleurLibelle: string;
	ombre?: string;
	taille?: number;
}> = ({valeur, decimales = 0, prefixe = '', suffixe = '', libelle, t, duree, couleur, couleurLibelle, ombre, taille = 190}) => {
	const progression = interpolate(t, [0.15, Math.min(duree - 0.4, 1.6)], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	const arrivee = interpolate(t, [0, 0.4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: doux});
	return (
		<div style={{textAlign: 'center', opacity: arrivee, translate: `0px ${interpolate(arrivee, [0, 1], [30, 0])}px`}}>
			<div
				style={{
					fontFamily: TITRE,
					fontWeight: 600,
					fontSize: taille,
					lineHeight: 1,
					color: couleur,
					textShadow: ombre,
					fontVariantNumeric: 'tabular-nums',
				}}
			>
				{prefixe}
				{nombreFr(valeur * progression, decimales)}
				<span style={{fontStyle: 'italic', fontWeight: 400, fontSize: taille * 0.55}}>{suffixe}</span>
			</div>
			{libelle ? (
				<div
					style={{
						marginTop: 18,
						fontFamily: TEXTE,
						fontWeight: 600,
						fontSize: 30,
						letterSpacing: '0.3em',
						textTransform: 'uppercase',
						color: couleurLibelle,
						textShadow: ombre,
					}}
				>
					{libelle}
				</div>
			) : null}
		</div>
	);
};

export const Compteur: React.FC<{e: EffetDe<'compteur'>}> = ({e}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const duree = e.fin - e.debut;
	return (
		<AbsoluteFill style={{opacity: enveloppe(t, 0, duree, 0.01, 0.3)}}>
			{/* carte crème posée, coins arrondis, ombre douce : lisible sur n'importe quel plan */}
			<div
				style={{
					position: 'absolute',
					left: 110,
					right: 190,
					top: 1150,
					padding: '40px 20px 44px',
					borderRadius: 36,
					backgroundColor: COULEURS.creme,
					boxShadow: '0 24px 70px rgba(62,32,40,0.25)',
					scale: String(interpolate(t, [0, 0.45], [0.9, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: doux})),
				}}
			>
				<Chiffre {...e} t={t} duree={duree} couleur={COULEURS.bordeaux} couleurLibelle={COULEURS.noir} taille={170} />
			</div>
		</AbsoluteFill>
	);
};
