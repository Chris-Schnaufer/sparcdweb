'use client'

/** @module components/MoveUploads */

import * as React from 'react';
import {
  Button,
  Checkbox,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  Radio,
  RadioGroup,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

import ModalDialog from './ModalDialog';
import { CollectionsInfoContext, UserNameContext } from '../serverInfo';
import WorkspaceOverlay from './WorkspaceOverlay';

const SUCCESS_WINDOW_AUTOCLOSE_MS = 3 * 60 * 1000; // How long to wait before auto-closing the success window

/**
 * Function that handles managing uploads for a collection
 * @function
 * @param {string} collectionId The id of the collection the upload is in
 * @param {object} upload The upload item to be moved
 * @param {boolean} admin The user is believed to be an admin
 * @param {Array} [buckets] The buckets that are not collections. Don't specify if not admin
 * @param {function} [getBuckets] Function to call if the non-collection buckets are needed. Don't specify if not admin
 * @param {function} onMove Function to call when the wants to move the upload
 * @param {function} onClose Function to call when the user is finished
 */
export default function MoveUploads({collectionId, upload, admin, buckets, getBuckets, onMove, onClose}) {
  const theme = useTheme();
  const collectionsItems = React.useContext(CollectionsInfoContext);
  const userName = React.useContext(UserNameContext);
  const successMessageTORef = React.useRef(null);     // Used to keep track of the success message timer
  const [showSuccessMessage, setShowSuccessMessage] = React.useState(false);
  const [selectedCollection, setSelectedCollection] = React.useState(null);
  const [showBuckets, setShowBuckets] = React.useState(false);  // Show additional destinations when admin

  // The base set of collections without the one containing the upload
  const baseCollections = React.useMemo(() => {
    return collectionsItems.filter((item) => item.id !== collectionId);
  }, [collectionsItems, collectionId]);

  // Filter out the allowed collections
  const filteredCollections = React.useMemo(() => {
    if (admin)  return baseCollections;

    // It takes longer to check all the &&, but using || in its places makes it less clear
    return baseCollections.filter((item) => item && 
            item.permissions && item.permissions.usernameProperty === userName &&
                                (item.permissions.ownerProperty || item.permissions.uploadProperty)
        );

  }, [admin, baseCollections, userName]);

  // Get the collection item information
  const collInfo = React.useMemo(() => {
    return collectionsItems.find((item) => item.id === collectionId);
  }, [collectionId, collectionsItems])

  /**
   * Handles the changing the show buckets checkbox
   * @function
   * @param {object} event The triggering event
   */
  const handleShowBucketsChange = React.useCallback((event) => {
    setShowBuckets(event.target.checked);
    if (!buckets && typeof getBuckets === 'function') {
      getBuckets();
    }
  }, [buckets, getBuckets]);

  /**
   * Gets the name of the currently selected collection
   * @function
   */
  const selectedCollectionName = React.useMemo(() => {
    if (!selectedCollection) return '';

    const name = filteredCollections.find((item) => item.id === selectedCollection)?.name
                 ?? buckets?.find((b) => b === selectedCollection);

    return name ? `: ${name}` : '';

  }, [filteredCollections, selectedCollection, buckets]);

  /**
   * Handles the success message closing
   * @function
   */
  const handleSuccessClose = React.useCallback(() => {
    setShowSuccessMessage(false);
    if (successMessageTORef.current !== null) {
      window.clearTimeout(successMessageTORef.current);
      successMessageTORef.current = null;
    }
    onClose();
  }, [onClose]);

  /**
   * Handle the user wanting to move a collection
   * @function
   */
  const handleMove = React.useCallback(() => {
    onMove?.(collectionId, upload, selectedCollection,
              (respData) => { // Success
                setShowSuccessMessage(true);
                successMessageTORef.current = window.setTimeout(handleSuccessClose, SUCCESS_WINDOW_AUTOCLOSE_MS);
              }
    )
  }, [collectionId, handleSuccessClose, onMove, selectedCollection, upload]);

  /**
   * Function to handle selected collection
   * @function
   * @param {object} event The triggering event
   */
  const handleSelectedCollection = React.useCallback((event) => {
    setSelectedCollection(event.target.value);
  }, []);

  return (
    <React.Fragment>
      <ModalDialog backgroundColor='rgba(218, 232,242,1)' extraSx={null} open={true} maxWidth='md' onClose={onClose}>
        <DialogTitle>Move Upload</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Moving upload <span style={{fontStyle:'italic'}}>{upload.name}</span> from collection {collInfo?.name}
          </DialogContentText>
          <Grid container direction="column" alignItems="start" justifyContent="start">
            { admin &&
              <FormControlLabel
                sx={{ mt: 2 }}
                control={
                  <Checkbox
                    checked={showBuckets}
                    onChange={handleShowBucketsChange}
                  />
                }
                label="Show all buckets"
              />
            }
            <FormControl component="fieldset" sx={{ mt: 2, width: '100%',}}>
              <FormLabel component="legend">Move To {selectedCollectionName}</FormLabel>
              <RadioGroup value={selectedCollection} onChange={handleSelectedCollection}
                          sx={{border:'1px solid grey', paddingLeft:'10px', backgroundColor:'rgba(238, 254,254,0.3)',
                                maxHeight:'40vh', overflowY:'auto', flexDirection:'column', flexWrap: 'nowrap',
                              }}
              >
                {filteredCollections.map((collection) => (
                  <FormControlLabel key={collection.id} value={collection.id} control={<Radio />} label={collection.name} />
                  ))
                }

                {showBuckets && buckets && 
                  buckets.map((bucket) => (
                      <FormControlLabel key={bucket} value={bucket} control={<Radio />} label={bucket} />
                  ))
                }
              </RadioGroup>
            </FormControl>
          </Grid>
          { !admin && 
            <DialogContentText>
              Only collections that you are allowed to write to are shown
            </DialogContentText>
          }
        </DialogContent>
        <DialogActions>
          <Button onClick={handleMove} disabled={!selectedCollection}>Move</Button>
          <Button onClick={onClose}>Done</Button>
        </DialogActions>
      </ModalDialog>
      { showSuccessMessage && 
        <WorkspaceOverlay>
            <Typography gutterBottom variant="body2" color="lightgrey">
              Upload {upload.name} has been successfully moved
            </Typography>
            <Button onClick={handleSuccessClose}>OK</Button>
        </WorkspaceOverlay>
      }
    </React.Fragment>
  );
};

MoveUploads.propTypes = {
  collectionId: PropTypes.string.isRequired,
  upload: PropTypes.shape({
    name: PropTypes.string.isRequired,
    id:   PropTypes.string.isRequired,
  }).isRequired,
  admin: PropTypes.bool,
  buckets: PropTypes.arrayOf(PropTypes.string),
  getBuckets: PropTypes.func,
  onMove: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};

MoveUploads.defaultProps = {
  admin:      false,
  buckets:    null,
  getBuckets: null,
};
