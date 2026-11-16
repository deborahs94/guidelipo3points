import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux} from '../outils';
import {SOUS_TITRES, TEXTE, TITRE, ZONE, teinte} from '../style';
import type {Legende} from '../types';

type Page = {mots: Legende[]; debut: number; fin: number};

/** 2 à 4 mots par écran : on coupe à la ponctuation, sur une pause, ou au 4e mot. */
const paginer = (legendes: Legende[]): Page[] => {
	const pages: Page[] = [];
	let cur: Legende[] = [];
	legendes.forEach((m, i) => {
		cur.push(m);
		const suivant = legendes[i + 1];
		const pause = suivant ? suivant.startMs - m.endMs > 450 : true;
		const ponctuation = /[.,!?…;:]$/.test(m.text.trim()) && cur.length >= 2;
		if (cur.length >= SOUS_TITRES.motsMax || pause || ponctuation || !suivant) {
			pages.push({mots: cur, debut: cur[0].startMs / 1000, fin: m.endMs / 1000});
			cur = [];
		}
	});
	// chaque page reste affichée jusqu'au début de la suivante (au plus 0,6 s après son dernier mot)
	return pages.map((pg, i) => ({...pg, fin: Math.min(pages[i + 1]?.debut ?? Infinity, pg.fin + 0.6)}));
};

export const SousTitres: React.FC<{legendes: Legende[]; fondClair: boolean; masque: (t: number) => boolean}> = ({
	legendes,
	fondClair,
	masque,
}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	const pages = useMemo(() => paginer(legendes), [legendes]);
	const page = pages.find((pg) => t >= pg.debut && t < pg.fin);
	if (!page || masque(t)) return null;
	const c = teinte(fondClair);

	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				style={{
					width: width - ZONE.gauche - ZONE.droite,
					translate: `${(ZONE.gauche - ZONE.droite) / 2}px 60px`,
					display: 'flex',
					flexWrap: 'wrap',
					justifyContent: 'center',
					alignItems: 'baseline',
					columnGap: 18,
					rowGap: 6,
				}}
			>
				{page.mots.map((m, i) => {
					const debut = m.startMs / 1000;
					const suivant = page.mots[i + 1];
					const finActif = suivant ? suivant.startMs / 1000 : m.endMs / 1000 + 0.15;
					const estActif = t >= debut && t < finActif;
					const apparition = interpolate(t, [debut - 0.04, debut + 0.1], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
						easing: doux,
					});
					return (
						<span
							key={i}
							style={{
								fontFamily: m.motCle ? TITRE : TEXTE,
								fontStyle: m.motCle ? 'italic' : 'normal',
								fontWeight: m.motCle ? 400 : 500,
								fontSize: m.motCle ? SOUS_TITRES.tailleMotCle : SOUS_TITRES.taille,
								lineHeight: 1.15,
								color: estActif || m.motCle ? c.accent : c.texte,
								textShadow: c.ombre,
								opacity: apparition,
								translate: `0px ${interpolate(apparition, [0, 1], [14, 0])}px`,
								scale: String(interpolate(apparition, [0, 1], [0.94, 1])),
							}}
						>
							{m.text.trim()}
						</span>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
