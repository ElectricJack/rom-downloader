

Rom-downloader is a tool that should make it easy to download and install roms onto a baltocera linux machine remotely. The goal is to be able to easily queue up a bunch of downloads, and then download one by one, and copy the rom to the target directory. The target directory will be a subfolder under a network drive. (\\BATOCERA\share\roms)

When we run the app we need to select where we are going to attempt to download the roms from, and the target folder they will get deployed to. This should be configured in a config file for each game system type, so the config will have a list of game system types, and for each it will have a link to a page where the roms can be downloaded, as well as a path to the subfolder where the roms should be installed. It should also have a path to the parent folder (network drive) which will contain all the target rom subfolders.

When we start the app there should be a dropdown to select the platform we want to download roms for. Then it should scrape the URL for the platform looking for rom downloads (usually zip files, but may be other formats, perhaps a list of formats can also be specified in the config file?)

An example URL in this case for the Nintendo GameCube platform can be viewed here: https://myrient.erista.me/files/Redump/Nintendo%20-%20GameCube%20-%20NKit%20RVZ%20[zstd-19-128k]/

The app should read the page and enumerate a list of potential downloads. 
Then the app should attempt to group duplicates (ideally only referencing a specific region, in this case we only want USA/English versions)

Then the app should display a list where we can check the games we want to download and install. Ideally we can scan the network drive and also see which games are already installed. (This should only happen once on initialization)

After the user selects some games, the list should be saved to disk so that if we load the app again and select the same platform (GameCube in this case) the selection is loaded back up. This will be helpful if the app terminates or needs to be restarted.

Finally the app should start downloading and installing each game that is not already installed. It should download the file right to the network share location. IF this is not possible, it should download to a local temp directory, and then move to the network share directory, and finally delete the temporary file. It is important that we only download one file at a time, and that we pause for a random duration of seconds between downloads. This wait time should be configurable in the settings file as well.