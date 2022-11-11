# Cars2TheVideoGameModding
Tools for modding Cars 2: The Video Game and other Avalanche games like Toy Story 3 or Disney Infinity.

THIS PROJECT IS IN NO WAY ASSOCIATED WITH *DISNEY*, *DISNEY INTERACTIVE*, *AVALANCHE SOFTWARE* OR *Warner Bros. Interactive Entertainment*.

#### [why](/src/c2ditools/archives/why.py)
A tool to pack unencrypted zips for Cars 2, Toy Story 3 and Disney Infinity 1.0 and 2.0.
Run it using `python -m c2ditools why <inputfolder> <outputfile>`. 
It will create a zip with all the files in the inputfolder.

#### [whyjustwhy](/src/c2ditools/archives/whyjustwhy.py)
A tool to pack encrypted zips for Disney Infinity 3.0.<br>
⚠ Untested<br>
Run it using `python -m c2ditools whyjustwhy <inputfolder> <outputfile>`. 
It will create a zip with all the files in the inputfolder.

#### [scene_dec](/src/c2ditools/scene/scene_dec.py)
A tool to convert files in the scene format (.oct, .bent etc.) to xml and extract the textures.
Run it using `python -m c2ditools scene_dec <inputfile> <outputfile> -t <texture folder>`.
It will create a xml and store all the textures in "texture folder" if you specified one.

#### [scene_enc](/src/c2ditools/scene/scene_enc.py)
A tool to convert xml files, that were generated by scene_dec, back to the scene format.
Run it using `python -m c2ditools scene_enc <inputfile> <outputfile> -t <texture folder> -c`.
It will create a scene file. If you specified a texture folder in scene_dec please specify the same folder in
scene_enc. If you use the `-c` flag it will create scene files for consoles using big endian.
