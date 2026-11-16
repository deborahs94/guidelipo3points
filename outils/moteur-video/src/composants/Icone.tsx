import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {COULEURS, TEXTE} from '../style';
import type {EffetDe} from '../types';

const TRACES: Record<EffetDe<'icone'>['icone'], React.ReactNode> = {
	coeur: <path d="M50 80 C20 60 12 42 22 30 C32 18 46 22 50 34 C54 22 68 18 78 30 C88 42 80 60 50 80 Z" />,
	check: <polyline points="26,52 44,70 76,32" />,
	etoile: <polygon points="50,14 60,40 88,40 65,57 74,84 50,68 26,84 35,57 12,40 40,40" />,
	goutte: <path d="M50 14 C50 14 26 46 26 62 A24 24 0 0 0 74 62 C74 46 50 14 50 14 Z" />,
	eclair: <polygon points="56,10 24,56 46,56 40,90 76,40 54,40" />,
	cible: (
		<>
			<circle cx="50" cy="50" r="32" />
			<circle cx="50" cy="50" r="18" />
			<circle cx="50" cy="50" r="4" />
		</>
	),
};

const POSITIONS = {droite: [800, 640], gauche: [270, 640], haut: [540, 470]} as const;

/** Icône qui apparaît avec un rebond et une gerbe de particules. */
export const Icone: React.FC<{e: EffetDe<'icone'>; fondClair: boolean}> = ({e, fondClair}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const duree = e.fin - e.debut;
	const [cx, cy] = POSITIONS[e.position ?? 'droite'];
	const rebond = interpolate(t, [0, 0.7], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.spring({damping: 7, mass: 0.6}),
	});
	const sortie = interpolate(t, [duree - 0.25, duree], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const taille = 190;

	return (
		<AbsoluteFill>
			{Array.from({length: 16}).map((_, i) => {
				const angle = (i / 16) * Math.PI * 2 + random(`a${i}`) * 0.4;
				const dist = 120 + random(`d${i}`) * 130;
				const p = interpolate(t, [0.08, 0.95], [0, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
					easing: Easing.out(Easing.cubic),
				});
				const r = 7 + random(`r${i}`) * 9;
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							left: cx - r,
							top: cy - r,
							width: r * 2,
							height: r * 2,
							borderRadius: i % 3 === 0 ? 2 : r,
							rotate: `${45 + p * 180}deg`,
							backgroundColor: i % 2 ? COULEURS.bordeaux : fondClair ? COULEURS.nude : COULEURS.creme,
							translate: `${Math.cos(angle) * dist * p}px ${Math.sin(angle) * dist * p}px`,
							scale: String(1 - p * 0.7),
							opacity: p > 0 ? interpolate(p, [0, 0.15, 1], [0, 1, 0]) : 0,
						}}
					/>
				);
			})}
			<div
				style={{
					position: 'absolute',
					left: cx - taille / 2,
					top: cy - taille / 2,
					width: taille,
					height: taille,
					borderRadius: taille,
					backgroundColor: COULEURS.creme,
					border: `5px solid ${COULEURS.bordeaux}`,
					boxShadow: '0 18px 50px rgba(62,32,40,0.28)',
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
					scale: String(rebond * sortie),
					rotate: `${interpolate(rebond, [0, 1], [-25, 0])}deg`,
				}}
			>
				<svg
					viewBox="0 0 100 100"
					width={taille * 0.58}
					height={taille * 0.58}
					fill="none"
					stroke={COULEURS.bordeaux}
					strokeWidth={8}
					strokeLinecap="round"
					strokeLinejoin="round"
				>
					{TRACES[e.icone]}
				</svg>
			</div>
			{e.texte ? (
				<div
					style={{
						position: 'absolute',
						left: cx - 170,
						width: 340,
						top: cy + taille / 2 + 22,
						textAlign: 'center',
						padding: '12px 0',
						borderRadius: 40,
						backgroundColor: COULEURS.creme,
						boxShadow: '0 10px 30px rgba(62,32,40,0.18)',
						fontFamily: TEXTE,
						fontWeight: 600,
						fontSize: 26,
						letterSpacing: '0.3em',
						textTransform: 'uppercase',
						color: COULEURS.noir,
						opacity: interpolate(t, [0.3, 0.6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) * sortie,
					}}
				>
					{e.texte}
				</div>
			) : null}
		</AbsoluteFill>
	);
};
