import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux, enveloppe, entree} from '../outils';
import type {Props} from '../types';

// Cadrages qui alternent à chaque coupe (échelle, décalage en px)
const CADRAGES = [
	{echelle: 1.0, x: 0, y: 0},
	{echelle: 1.16, x: 0, y: 70}, // plus serré sur le visage
	{echelle: 1.08, x: -40, y: 30},
];

export const CARTE = {echelle: 0.42, haut: 270, rayon: 44};

const PAN = 0.2; // durée d'une moitié de panoramique rapide (s)

/** Calcule la caméra à l'instant t (sans hook : sert aussi à mesurer la vitesse pour le flou). */
const camera = (t: number, p: Props, largeur: number) => {
	const bornes = [0, ...p.coupes.filter((c) => c > 0 && c < p.duree).sort((a, b) => a - b), p.duree];
	let i = 0;
	while (i < bornes.length - 2 && t >= bornes[i + 1]) i++;
	const cadre = CADRAGES[i % CADRAGES.length];
	// lente avancée sur tout le plan
	const avance = interpolate(t, [bornes[i], bornes[i + 1]], [1, 1.045], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	// zooms ponctuels
	let zoom = 1;
	for (const e of p.effets) {
		if (e.type === 'zoom') zoom *= 1 + ((e.force ?? 1.25) - 1) * enveloppe(t, e.debut, e.fin, 0.35, 0.35);
	}
	// panoramique rapide : sort à gauche avant la coupe, revient de la droite après
	let pan = 0;
	for (const e of p.effets) {
		if (e.type !== 'transition' || e.style !== 'panoramique') continue;
		if (t >= e.debut - PAN && t < e.debut)
			pan = interpolate(t, [e.debut - PAN, e.debut], [0, -largeur * 0.7], {easing: entree});
		else if (t >= e.debut && t < e.debut + PAN)
			pan = interpolate(t, [e.debut, e.debut + PAN], [largeur * 0.7, 0], {easing: doux});
	}
	return {echelle: cadre.echelle * avance * zoom, x: cadre.x * zoom + pan, y: cadre.y * zoom, zoom, pan};
};

export const Plan: React.FC<{p: Props}> = ({p}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const t = frame / fps;
	const c = camera(t, p, width);
	const avant = camera(t - 1 / fps, p, width);
	// flou de mouvement proportionnel à la vitesse du zoom (flou global) et du panoramique (flou horizontal).
	// Les changements de cadrage aux coupes sont des sauts voulus : ils ne comptent pas.
	const flouZoom = Math.min(10, Math.abs(c.zoom - avant.zoom) * 160);
	const flouPan = Math.min(60, Math.abs(c.pan - avant.pan) * 0.12);

	// passage en carte arrondie (vidéo réduite en haut, animation en dessous)
	let carte = 0;
	for (const e of p.effets) if (e.type === 'carte') carte = Math.max(carte, enveloppe(t, e.debut, e.fin, 0.5, 0.45));
	const echelleCarte = interpolate(carte, [0, 1], [1, CARTE.echelle]);
	const decalageCarte = interpolate(carte, [0, 1], [0, CARTE.haut + (height * CARTE.echelle) / 2 - height / 2]);

	const etalonnage = p.ambiance.etalonnage !== false;
	return (
		<AbsoluteFill
			style={{
				scale: String(echelleCarte),
				translate: `0px ${decalageCarte}px`,
				borderRadius: (CARTE.rayon / CARTE.echelle) * carte,
				overflow: 'hidden',
				boxShadow: carte > 0 ? `0 ${40 * carte}px ${120 * carte}px rgba(62,32,40,${0.35 * carte})` : undefined,
			}}
		>
			<svg width="0" height="0" style={{position: 'absolute'}}>
				<filter id="flou-pan">
					<feGaussianBlur stdDeviation={`${flouPan} 0`} />
				</filter>
			</svg>
			<AbsoluteFill
				style={{
					scale: String(c.echelle),
					translate: `${c.x}px ${c.y}px`,
					filter: [
						etalonnage ? 'brightness(1.03) contrast(1.04) saturate(1.03)' : '',
						flouZoom > 0.3 ? `blur(${flouZoom}px)` : '',
						flouPan > 0.5 ? 'url(#flou-pan)' : '',
					].join(' '),
				}}
			>
				<Video src={staticFile(p.video)} objectFit="cover" style={{width: '100%', height: '100%'}} />
			</AbsoluteFill>
			{etalonnage ? (
				// très légère chaleur (+3 à +5 dans CapCut)
				<AbsoluteFill
					style={{backgroundColor: `rgba(255,170,110,${p.ambiance.chaleur ?? 0.06})`, mixBlendMode: 'soft-light'}}
				/>
			) : null}
		</AbsoluteFill>
	);
};
