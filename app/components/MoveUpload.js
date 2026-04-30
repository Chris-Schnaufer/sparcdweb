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
  Divider,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  Radio,
  RadioGroup,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

import ModalDialog from './ModalDialog';
import { CollectionsInfoContext, UserNameContext } from '../serverInfo';

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
  const collectionsItems = React.useContext(CollectionsInfoContext);
  const userName = React.useContext(UserNameContext);
  const [selectedCollection, setSelectedCollection] = React.useState(null);
  const [showBuckets, setShowBuckets] = React.useState(false);  // Show additional destinations when admin

  // Filter out the allowed collections
  const filteredCollections = React.useMemo(() => {
    if (admin)  return collectionsItems;

    // It takes longer to check all the &&, but using || in its places makes it less clear
    return collectionsItems.filter((item) => item && item.id !== collectionId &&
            item.permissions && item.permissions.usernameProperty === userName &&
                                (item.permissions.ownerProperty || item.permissions.uploadProperty)
        );

  }, [collectionsItems, userName]);

  // Get the collection item information
  const collInfo = React.useMemo(() => {
    return collectionsItems.filter((item) => item.id === collectionId);
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
  const getSelectedCollectionName = React.useCallback(() => {
    if (!selectedCollection || !filteredCollections) return '';

    const name = filteredCollections.find((item) => item.id === selectedCollection)?.name;
    return name ? `: ${name}` : '';

  }, [filteredCollections, selectedCollection]);

  /**
   * Handle the user wanting to move a collection
   * @function
   */
  const handleMove = React.useCallback(() => {
    onMove?.(collectionId, upload, selectedCollection,
              (respData) => { // Success
                onClose();
              },
              (err) =>  {     // Failure
              }
    )
  }, [selectedCollection]);

  return (
    <ModalDialog backgroundColor='rgba(218, 232,242,1)' extraSx={null} open={true} maxWidth='md' onClose={onClose} children>
      <DialogTitle>Move Upload</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Moving upload <span style={{fontStyle:'italic'}}>{upload.name}</span> from collection {collInfo.name}
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
            <FormLabel component="legend">Move To {getSelectedCollectionName()}</FormLabel>
            <RadioGroup value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}
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
  );
};
