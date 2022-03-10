# Cars2TheVideoGameModding
Tools for modding Cars 2: The Video Game and other Avalanche games like Toy Story 3 or Disney Infinity.

#### [why](/src/c2ditools/archives/why.py)
A tool to pack zips for Cars 2. It requires atleast Python 3.8.
Run it using `python -m c2ditools why <inputfolder> <outputfile>`. 
It will create a zip with all the files in the inputfolder.

#### [scene_dec](/src/c2ditools/scene/scene_dec.py)
A tool to convert files in the scene format (.oct, .bent etc.) to xml and extract the textures.
Run it using `python -m c2ditools scene_dec <inputfile> <outputfile> <texture folder>`.
It will create a xml and store all the textures in "texture folder".
