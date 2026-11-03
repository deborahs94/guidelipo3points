import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux, enveloppe} from '../outils';
import {COULEURS, TEXTE, TITRE} from '../style';
import type {EffetDe} from '../types';
import {Chiffre} from './Compteur';
import {CARTE} from './Plan';

// Zone d'animation sous la carte vidéo (dans la zone sûre)
const PANNEAU = {haut: CARTE.haut + 1920 * CARTE.echelle + 40, gauche: 60, largeur: 880, hauteur: 400};
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const Entonnoir: React.FC<{etapes: string[]; t: number}> = ({etapes, t}) => {
	const teintes = [COULEURS.bordeaux, '#86303F', '#A3575F', COULEURS.nude];
	const h = Math.min(86, (PANNEAU.hauteur - 20) / etapes.length - 10);
	return (
		<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10}}>
			{etapes.map((txt, i) => {
				const p = interpolate(t, [0.45 + i * 0.28, 0.95 + i * 0.28], [0, 1], {
					...clamp,
					easing: Easing.spring({damping: 12}),
				});
				const largeur = 860 - i * (440 / Math.max(1, etapes.length - 1));
				const retrait = 40;
				return (
					<div
						key={i}
						style={{
							width: largeur,
							height: h,
							backgroundColor: teintes[i % teintes.length],
							clipPath: `polygon(0 0, 100% 0, calc(100% - ${retrait}px) 100%, ${retrait}px 100%)`,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							fontFamily: TEXTE,
							fontWeight: 600,
							fontSize: 28,
							letterSpacing: '0.22em',
							textTransform: 'uppercase',
							color: COULEURS.creme,
							opacity: Math.min(1, p * 1.5),
							translate: `0px ${interpolate(p, [0, 1], [-50, 0])}px`,
							scale: `${interpolate(p, [0, 1], [0.8, 1])} 1`,
						}}
					>
						{txt}
					</div>
				);
			})}
		</div>
	);
};

const Chat: React.FC<{question: string; reponse: string; nom: string; t: number; duree: number}> = ({
	question,
	reponse,
	nom,
	t,
	duree,
}) => {
	const debutFrappe = 0.55;
	// 26 caractères/s, plus vite si la carte est courte : la frappe tient dans 35 % de la carte
	const vitesse = Math.max(26, question.length / Math.max(0.5, duree * 0.35));
	const finFrappe = debutFrappe + question.length / vitesse;
	const nbQ = Math.floor(interpolate(t, [debutFrappe, finFrappe], [0, question.length], clamp));
	const debutReponse = Math.min(finFrappe + 0.7, duree * 0.62);
	const points = t > finFrappe + 0.1 && t < debutReponse;
	const pRep = interpolate(t, [debutReponse, debutReponse + 0.35], [0, 1], {...clamp, easing: Easing.spring({damping: 13})});
	const motsRep = reponse.split(' ');
	const nbRep = Math.floor(interpolate(t, [debutReponse, debutReponse + motsRep.length * 0.07], [0, motsRep.length], clamp));
	const bulle: React.CSSProperties = {
		maxWidth: 660,
		padding: '16px 24px',
		borderRadius: 26,
		fontFamily: TEXTE,
		fontWeight: 500,
		fontSize: 29,
		lineHeight: 1.3,
	};
	return (
		<div
			style={{
				width: PANNEAU.largeur,
				height: PANNEAU.hauteur,
				backgroundColor: COULEURS.blanc,
				borderRadius: 30,
				boxShadow: '0 20px 60px rgba(62,32,40,0.18)',
				overflow: 'hidden',
				display: 'flex',
				flexDirection: 'column',
			}}
		>
			<div
				style={{
					height: 64,
					display: 'flex',
					alignItems: 'center',
					gap: 14,
					padding: '0 26px',
					borderBottom: `1px solid ${COULEURS.lin}`,
					fontFamily: TEXTE,
					fontWeight: 600,
					fontSize: 22,
					letterSpacing: '0.25em',
					textTransform: 'uppercase',
					color: COULEURS.noir,
				}}
			>
				<div style={{width: 14, height: 14, borderRadius: 7, backgroundColor: COULEURS.bordeaux}} />
				{nom}
			</div>
			<div style={{flex: 1, padding: 22, display: 'flex', flexDirection: 'column', gap: 14}}>
				<div
					style={{
						...bulle,
						alignSelf: 'flex-end',
						backgroundColor: COULEURS.bordeaux,
						color: COULEURS.creme,
						opacity: t > debutFrappe - 0.1 ? 1 : 0,
					}}
				>
					{question.slice(0, nbQ)}
					<span style={{opacity: nbQ < question.length && Math.floor(t * 4) % 2 === 0 ? 1 : 0}}>|</span>
				</div>
				{points ? (
					<div style={{...bulle, alignSelf: 'flex-start', backgroundColor: COULEURS.lin, display: 'flex', gap: 8}}>
						{[0, 1, 2].map((i) => (
							<div
								key={i}
								style={{
									width: 12,
									height: 12,
									borderRadius: 6,
									backgroundColor: COULEURS.noir,
									opacity: 0.3 + 0.7 * Math.max(0, Math.sin(t * 9 - i * 0.9)),
								}}
							/>
						))}
					</div>
				) : null}
				{t >= debutReponse ? (
					<div
						style={{
							...bulle,
							alignSelf: 'flex-start',
							backgroundColor: COULEURS.lin,
							color: COULEURS.noir,
							scale: String(interpolate(pRep, [0, 1], [0.85, 1])),
							transformOrigin: '0% 100%',
							opacity: pRep,
						}}
					>
						{motsRep.map((m, i) => (
							<span key={i} style={{opacity: i < nbRep ? 1 : 0}}>
								{m}{' '}
							</span>
						))}
					</div>
				) : null}
			</div>
		</div>
	);
};

const Checklist: React.FC<{titre?: string; elements: string[]; t: number}> = ({titre, elements, t}) => (
	<div style={{paddingLeft: 40}}>
		{titre ? (
			<div
				style={{
					fontFamily: TITRE,
					fontStyle: 'italic',
					fontSize: 50,
					color: COULEURS.bordeaux,
					marginBottom: 18,
					opacity: interpolate(t, [0.4, 0.7], [0, 1], clamp),
				}}
			>
				{titre}
			</div>
		) : null}
		{elements.map((txt, i) => {
			const apparait = interpolate(t, [0.55 + i * 0.45, 0.85 + i * 0.45], [0, 1], {...clamp, easing: doux});
			const coche = interpolate(t, [0.85 + i * 0.45, 1.1 + i * 0.45], [0, 1], clamp);
			return (
				<div
					key={i}
					style={{
						display: 'flex',
						alignItems: 'center',
						gap: 26,
						marginBottom: 20,
						opacity: apparait,
						translate: `${interpolate(apparait, [0, 1], [-30, 0])}px 0px`,
					}}
				>
					<div
						style={{
							width: 50,
							height: 50,
							borderRadius: 12,
							border: `3px solid ${COULEURS.bordeaux}`,
							backgroundColor: coche > 0.2 ? COULEURS.bordeaux : 'transparent',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							scale: String(1 + 0.18 * Math.sin(Math.PI * coche)),
						}}
					>
						<svg viewBox="0 0 100 100" width={36} height={36}>
							<polyline
								points="20,54 42,74 82,30"
								fill="none"
								stroke={COULEURS.creme}
								strokeWidth={13}
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeDasharray={100}
								strokeDashoffset={100 * (1 - coche)}
							/>
						</svg>
					</div>
					<div style={{fontFamily: TEXTE, fontWeight: 500, fontSize: 36, color: COULEURS.noir}}>{txt}</div>
				</div>
			);
		})}
	</div>
);

/** Panneau animé qui joue sous la carte vidéo. */
export const Carte: React.FC<{e: EffetDe<'carte'>}> = ({e}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const duree = e.fin - e.debut;
	// le panneau disparaît avant que la vidéo ne reprenne tout l'écran
	const visible = enveloppe(t, 0.25, duree - 0.35, 0.35, 0.25);
	let contenu: React.ReactNode = null;
	if (e.contenu === 'entonnoir') contenu = <Entonnoir etapes={e.etapes} t={t} />;
	if (e.contenu === 'chat') contenu = <Chat question={e.question} reponse={e.reponse} nom={e.nom ?? 'Assistant IA'} t={t} duree={duree} />;
	if (e.contenu === 'checklist') contenu = <Checklist titre={e.titre} elements={e.elements} t={t} />;
	if (e.contenu === 'chiffre')
		contenu = (
			<div style={{paddingTop: 50}}>
				<Chiffre {...e} t={t - 0.3} duree={duree - 0.3} couleur={COULEURS.bordeaux} couleurLibelle={COULEURS.noir} taille={200} />
			</div>
		);
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					top: PANNEAU.haut,
					left: PANNEAU.gauche,
					width: PANNEAU.largeur,
					height: PANNEAU.hauteur,
					opacity: visible,
					translate: `0px ${interpolate(visible, [0, 1], [40, 0])}px`,
				}}
			>
				{contenu}
			</div>
		</AbsoluteFill>
	);
};
