'use client';

import { useState } from 'react';

import { ColorSwatchPicker, FileDropzone, NumberField, RangeSlider, SearchField, Slider } from '@/components/ui';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

export function FormsSection() {
  const [query, setQuery] = useState('');
  const [volume, setVolume] = useState(70);
  const [range, setRange] = useState<readonly [number, number]>([15, 60]);
  const [length, setLength] = useState<number | null>(30);
  const [colour, setColour] = useState('#f59e0b');
  const [brand, setBrand] = useState('#1d4ed8');
  const [files, setFiles] = useState<string[]>([]);
  const [rejected, setRejected] = useState<string>();

  return (
    <GallerySection id="forms" title="More inputs" intro="Search, sliders, numbers, colour and files. All keyboard-operable; drags always have a key or click equivalent.">
      <Specimen title="SearchField" note="Escape clears first. Clear button appears with text; a shortcut hint shows while empty.">
        <StateGrid className="lg:grid-cols-3">
          <State label="default" className="w-full">
            <SearchField value={query} onValueChange={setQuery} shortcut={['/']} placeholder="Search clips" className="w-full" />
          </State>
          <State label="loading results" className="w-full">
            <SearchField value="podcast" onValueChange={() => undefined} loading className="w-full" />
          </State>
          <State label="disabled" className="w-full">
            <SearchField value="" onValueChange={() => undefined} disabled className="w-full" />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="Slider and RangeSlider" note="role=slider; arrows step, Shift or Page keys ×10, Home/End. Thumbs of a range never cross.">
        <StateGrid className="lg:grid-cols-3">
          <State label="slider" className="w-full">
            <Slider label="Music volume" value={volume} onValueChange={setVolume} formatValue={(v) => `${v}%`} className="w-full" />
          </State>
          <State label="range" className="w-full">
            <RangeSlider
              label="Clip length"
              value={range}
              onValueChange={setRange}
              min={5}
              max={180}
              step={5}
              minGap={5}
              thumbLabels={['Shortest', 'Longest']}
              formatValue={(v) => `${v} s`}
              className="w-full"
            />
          </State>
          <State label="disabled" className="w-full">
            <Slider label="Caption size" defaultValue={40} disabled hint="Locked by the template." className="w-full" />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="NumberField" note="Typing is kept while editing and clamped on blur. ↑↓ step, Shift ×10.">
        <StateGrid className="lg:grid-cols-3">
          <State label="with unit" className="w-full">
            <NumberField label="Clip length" value={length} onValueChange={setLength} min={5} max={180} step={5} unit="s" />
          </State>
          <State label="error" className="w-full">
            <NumberField label="Clips to make" defaultValue={40} max={50} error="Your plan allows up to 20 per video." />
          </State>
          <State label="disabled" className="w-full">
            <NumberField label="Frame rate" defaultValue={30} disabled />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="ColorSwatchPicker" note="Token hues only, plus a brand colour for Brand Kit. Arrows move and select; the tick marks the choice.">
        <StateGrid className="lg:grid-cols-2">
          <State label="token palette">
            <ColorSwatchPicker label="Caption highlight" value={colour} onValueChange={setColour} />
          </State>
          <State label="with brand colour">
            <ColorSwatchPicker label="Brand colour" value={brand} onValueChange={setBrand} allowCustom hint="Used on your intro and end card." />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="FileDropzone" note="A real file input inside: click, Enter or Space opens the picker; drop is a shortcut.">
        <StateGrid className="lg:grid-cols-3">
          <State label="default" className="w-full">
            <FileDropzone
              title="Drop a video, or choose a file"
              hint="MP4, MOV or WebM, up to 4 GB"
              accept="video/*"
              maxSize={4 * 1024 ** 3}
              onFiles={(list) => setFiles(list.map((file) => file.name))}
              onReject={(list) => setRejected(list[0]?.reason)}
              error={rejected}
              compact
              className="w-full"
            />
            {files.length > 0 && <p className="text-cn-caption text-cn-fg-muted">Chosen: {files.join(', ')}</p>}
          </State>
          <State label="error" className="w-full">
            <FileDropzone title="Add a logo" hint="PNG or SVG" accept="image/png,.svg" onFiles={() => undefined} error="logo.gif is not a supported file type." compact className="w-full" />
          </State>
          <State label="disabled" className="w-full">
            <FileDropzone title="Upload" onFiles={() => undefined} disabled disabledReason="Storage is full. Delete clips or add storage to upload." compact className="w-full" />
          </State>
        </StateGrid>
      </Specimen>
    </GallerySection>
  );
}
