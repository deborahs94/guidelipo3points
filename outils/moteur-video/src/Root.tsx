import React from 'react';
import {Composition, type CalculateMetadataFunction} from 'remotion';
import props from '../props.json';
import {Signature} from './Signature';
import {chargerPolices} from './style';
import type {Props} from './types';

chargerPolices();

const calculateMetadata: CalculateMetadataFunction<Props> = ({props: p}) => ({
	durationInFrames: Math.round(p.duree * p.fps),
	fps: p.fps,
	width: p.largeur,
	height: p.hauteur,
});

export const RemotionRoot: React.FC = () => (
	<Composition
		id="Signature"
		component={Signature}
		durationInFrames={300}
		fps={30}
		width={1080}
		height={1920}
		defaultProps={props as unknown as Props}
		calculateMetadata={calculateMetadata}
	/>
);
