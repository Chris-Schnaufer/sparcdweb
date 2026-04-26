/** @module CollectionsManage */

import * as React from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import BorderColorOutlinedIcon from '@mui/icons-material/BorderColorOutlined';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import CircularProgress from '@mui/material/CircularProgress';
import EditNoteOutlinedIcon from '@mui/icons-material/EditNoteOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import WorkspaceOverlay from './components/WorkspaceOverlay';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

import EditUploadDetails from './components/EditUploadDetails';
import { Level } from './components/Messages';
import * as Server from './ServerCalls';
import { AddMessageContext, CollectionsInfoContext, NarrowWindowContext, SizeContext,
         TokenContext, TokenExpiredFuncContext } from './serverInfo';
import * as utils from './utils';

/**
 * Renders the UI for managing the list of uploaded folders
 * @function
 * @param {boolean} loadingCollections Indicates if collections are being loaded
 * @param {string} [selectedCollection] The currently selected collection name
 * @param {function} onSelectionChange Called when the user selects a new collection
 * @param {function} onEditUpload Called when the user wants to edit an upload of a collection
 * @param {function} searchSetup Call when settting up or clearing search elements
 * @param {function} onUploadUpdateMetadata Called when an upload's metadata is changed
 * @returns {object} The rendered UI
 */
export default function CollectionsManage({loadingCollections, selectedCollection, onSelectionChange, onEditUpload,
                                            searchSetup, onUploadUpdateMetadata}) {
  const theme = useTheme();
  const sidebarRef = React.useRef();
  const addMessage = React.useContext(AddMessageContext); // Function adds messages for display
  const collectionsItems = React.useContext(CollectionsInfoContext);
  const collectionToken = React.useContext(TokenContext);  // Login token
  const narrowWindow = React.useContext(NarrowWindowContext);
  const uiSizes = React.useContext(SizeContext);
  const setTokenExpired = React.useContext(TokenExpiredFuncContext);
  const serverURLRef = React.useRef(utils.getServer());    // The starting part of the url to call
  const [editingUploadMask, setEditingUploadMask] = React.useState(false);
  const [expandedUpload, setExpandedUpload] = React.useState(false);
  const [pendingMessage, setPendingMessage] = React.useState(null);
  const [searchIsSetup, setSearchIsSetup] = React.useState(false);
  const [selectionIndex, setSelectionIndex] = React.useState(-1);
  const [totalHeight, setTotalHeight] = React.useState(null);  // Default value is recalculated at display time
  const [uploadDetailEdit, setUploadDetailEdit] = React.useState(null);
  const [uploadSelectionIndex, setUploadSelectionIndex] = React.useState(-1);

  // Initialize collections information
  React.useEffect(() => {
    if (collectionsItems && selectedCollection.collectionName && (selectionIndex === -1 || selectionIndex >= collectionsItems.length)) {
      const collIndex = collectionsItems.findIndex((item) => item.name === selectedCollection.collectionName);
      setSelectionIndex(collIndex);
      if (collIndex >= 0 && selectedCollection.uploadKey) {
        setUploadSelectionIndex(collectionsItems[collIndex].uploads.findIndex((item) => item.key === selectedCollection.uploadKey));
      } else {
        setUploadSelectionIndex(-1);
      }
    }
  }, [collectionsItems, selectedCollection, selectionIndex]);

  // Recalcuate available space in the window
  React.useLayoutEffect(() => {
    // More size setup
    setTotalHeight(uiSizes.workspace.height);

  }, [narrowWindow, uiSizes]);


   // Scrolls the selected collection into view
  React.useLayoutEffect(() => {
    if (selectionIndex >= 0 && collectionsItems && selectionIndex < collectionsItems.length) {
      // Scroll the collection into view
      const collectionName = collectionsItems[selectionIndex].name;
      let el = document.getElementById("collection-"+collectionName);
      if (el) {
        el.scrollIntoView({behavior: 'instant', block: 'center', inline: 'center'});
      }

      if (uploadSelectionIndex >= 0 && uploadSelectionIndex < collectionsItems[selectionIndex].uploads.length) {
        el = document.getElementById('collection-upload-item-' + collectionsItems[selectionIndex].uploads[uploadSelectionIndex].name);
        if (el) {
          el.scrollIntoView({behavior: 'instant', block: 'center', inline: 'center'});
        }
      }
    }
  }, [collectionsItems, selectionIndex, uploadSelectionIndex])

  /**
   * Searches for collections that meet the search criteria and scrolls it into view
   * @function
   * @param {string} searchTerm The term to search in a collection
   */
  const handleCollectionSearch =  React.useCallback((searchTerm) => {
    const ucSearchTerm = searchTerm.toUpperCase();
    const foundCollections = collectionsItems.filter((item) => item.name.toUpperCase().includes(ucSearchTerm) ||
                                                               item.description.toUpperCase().includes(ucSearchTerm));
    // Scroll finding into view
    if (foundCollections.length > 0) {
      const elCollection = document.getElementById("collection-"+foundCollections[0].name);
      if (elCollection) {
        elCollection.scrollIntoView();
        elCollection.focus();
        setSelectionIndex(collectionsItems.findIndex((item) => item.name === foundCollections[0].name));
        searchSetup('Collection Name', handleCollectionSearch);
        return true;
      }
    }

    return false;
  }, [collectionsItems, searchSetup]);

  /**
   * Handle the user wanting to edit an upload
   * @function
   */
  const handleUploadEdit = React.useCallback((curCollectionId, itemKey) => {
    setEditingUploadMask(true);
    window.setTimeout(() => {
        onEditUpload(curCollectionId, itemKey, "Collections", () => {}, () => setEditingUploadMask(false));
    }, 200);
  }, [collectionsItems, onEditUpload, selectionIndex]);

  /**
   * Returns a function that will set the expanded panel name for Accordian panels
   * @function
   * @param {string} panelName Unique identifier of the panel
   * @returns {function} A function that will handle the accordian state change
   */
  function handleExpandedChange(panelName) {
    return (event, isExpanded) => {
      setExpandedUpload(isExpanded ? panelName : false);
    }
  }

  /**
   * Handler for users wanting to edit upload details
   * @function
   * @param {string} upload The ID of the collection the upload belongs to
   * @param {object} upload The upload information to edit
   */
  const handleUploadDetailsEdit = React.useCallback((collectionId, upload) => {
    setUploadDetailEdit({collectionId, upload});
  }, []);

  /**
   * Handles an edit change to an upload detail
   * @function
   * @param {Array} uploads The list of uploads related to the request
   * @param {string} comment The updated comment
   * @param {object} upload The upload associated with this change
   * @param {function} [onSuccess] The function to call upon success
   * @param {function} [onFailure] The function to call upon filure
   */
  const handleUploadDetailChange = React.useCallback((upload, comment, onSuccess, onFailure) => {

    onSuccess ||= () => {};
    onFailure ||= () => {};

    if (!uploadDetailEdit) {
      addMessage(Level.Error, 'Unable to find the upload to modify');
      return;
    }
    // Somehow we aren't the current edit
    if (upload.key !== uploadDetailEdit.upload.key) {
      return;
    }

    setPendingMessage('Please wait while making the changes to the upload details');
    const success = Server.updateUploadDetails(serverURLRef.current, collectionToken,
                                uploadDetailEdit.collectionId,
                                upload.key,
                                comment,
                                setTokenExpired,
                                (respData) => {   // Success
                                  setPendingMessage(null);
                                  if (respData.success) {
                                    setUploadDetailEdit(null);
                                    onSuccess(upload.key);
                                    // Reload the collections
                                    onUploadUpdateMetadata();
                                  } else {
                                    addMessage(Level.Error, 'Unable to update the collection details');
                                    onFailure(upload.key);
                                  }
                                },
                                (err) => {        // Failure
                                  addMessage(Level.Error, 'An problem occurred while updating the upload information');
                                  onFailure(upload.key);
                                  setPendingMessage(null);
                                }
    );

    if (!success) {
      addMessage(Level.Error, 'An unknown problem occurred while updating the upload information');
      onFailure(key);
    }

  }, [addMessage, collectionToken, serverURLRef, setTokenExpired, uploadDetailEdit]);

  /**
   * Handler for when the user's selection changes and prevents default behavior
   * @function
   * @param {object} event The event
   * @param {string} bucket The bucket of the new selected collection
   * @param {string} id The ID of the new selected collection
   */
  const onCollectionChange = React.useCallback((event, bucket, id) => {
    event.preventDefault();

    const collIndex = collectionsItems.findIndex((item) => item.bucket === bucket && item.id === id);
    setSelectionIndex(collIndex);

    onSelectionChange(collectionsItems[collIndex].name);
  }, [collectionsItems, onSelectionChange]);

  /**
   * Formats the upload timestamp for display
   * @function
   * @param {object} uploadTS The timestamp object from an upload
   * @returns {string} Returns the formatted timestamp string
   */
  function getLastUploadDate(uploadTS) {
    let returnStr = '';
    if (uploadTS) {
      if (uploadTS.date) {
        if (uploadTS.date.year) {
          returnStr += utils.pad(uploadTS.date.year);
        } else {
          returnStr += 'XXXX';
        }
        if (uploadTS.date.month) {
          returnStr += '-' + utils.pad(uploadTS.date.month, 2, 0);
        } else {
          returnStr += '-XX';
        }
        if (uploadTS.date.day) {
          returnStr += '-' + utils.pad(uploadTS.date.day, 2, 0);
        } else {
          returnStr += '-XX';
        }
      }

      if (uploadTS.time) {
        if (uploadTS.time.hour !== null) {
          returnStr += ' ' + utils.pad(uploadTS.time.hour, 2, 0);
        } else {
          returnStr += ' XX';
        }
        if (uploadTS.time.minute !== null) {
          returnStr += ':' + utils.pad(uploadTS.time.minute, 2, 0);
        } else {
          returnStr += ':XX';
        }
        if (uploadTS.time.second !== null) {
          returnStr += ':' + utils.pad(uploadTS.time.second, 2, 0);
        } else {
          returnStr += ':XX';
        }
      }
    }

    if (returnStr.length <= 0) {
      returnStr = 'No last upload date';
    }

    return returnStr;
  }

  // Setup search
  React.useLayoutEffect(() => {
    if (!searchIsSetup) {
      searchSetup('Collection Name', handleCollectionSearch);
      setSearchIsSetup(true);
    }
  }, [handleCollectionSearch, searchIsSetup, searchSetup]);

  // Render the UI
  const curHeight = (totalHeight || 480) + 'px';
  const curCollection = collectionsItems && selectionIndex >= 0 ? collectionsItems[selectionIndex] : { uploads: [] };
  return (
    <Box id='collection-manage-workspace-wrapper'>
      <Grid id='collection-manage-workspace' container direction='row' alignItems='start' justifyContent='start' sx={{ width:'100vw' }} columns={48}>
        <div id='collection-manage-workspace-collections-wrapper' 
                style={{minWidth:'calc(100vw - 460px)', maxWidth:'calc(100vw - 460px)', maxHeight:curHeight, paddingLeft:'10px', overflowY:'scroll'}}>
          <Grid id='collection-manage-workspace-collections-details' container direction="row" >
            { collectionsItems && collectionsItems.map((item, idx) =>
              <Grid key={'collection-'+item.name+'-'+idx} >
                    <Grid display='flex' justifyContent='left' size='grow' >
                      <Card id={"collection-"+item.name}
                            onClick={(event) => onCollectionChange(event, item.bucket, item.id)}
                            variant="outlined"
                            data-active={selectionIndex === idx ? '' : undefined}
                            sx={{border:'2px solid rgba(128, 128, 185, 0.5)', borderRadius:'15px', minWidth:'400px', maxWidth:'400px',
                                  backgroundColor:'rgba(218, 232,242,0.7)',
                                  '&[data-active]': {borderColor:'rgba(155, 175, 202, 0.85)'},
                                  '&:hover':{backgroundColor:'rgba(185, 185, 185, 0.25)'}
                                }}
                      >
                        <CardActionArea data-active={selectionIndex === idx ? '' : undefined}
                          sx={{height: '100%',  '&[data-active]': {backgroundColor:'rgba(64, 64, 64, 0.23)'} }}
                        >
                          <CardContent>
                            <Grid container direction="column" spacing={1}>
                              <Grid>
                                <Typography variant='body' sx={{fontSize:'larger', fontWeight:(selectionIndex === idx ? 'bold' : 'normal')}}>
                                  {item.name}
                                </Typography>
                              </Grid>
                              <Grid>
                                <Typography variant="body">
                                  {item.organization}
                                </Typography>
                              </Grid>
                              <Grid>
                                <Typography variant="body" sx={{whiteSpace:"pre-wrap"}} >
                                  {item.description}
                                </Typography>
                              </Grid>
                              <Grid>
                                <Typography variant="body">
                                  Uploads - {item.uploads.length}
                                </Typography>
                              </Grid>
                              { item.uploads.length > 0 &&
                                <Grid>
                                  <Typography variant="body">
                                    Last upload: {getLastUploadDate(item.last_upload_ts)}
                                  </Typography>
                                </Grid>
                              }
                          </Grid>
                          </CardContent>
                        </CardActionArea>
                      </Card>
                    </Grid>
              </Grid>
            )}
          </Grid>
        </div>
        <div id='collection-manage-workspace-uploads-wrapper' style={{minWidth:'460px', maxWidth:'460px', maxHeight:curHeight, paddingRight:'10px', overflowY:"scroll"}}>
          <Grid id='collection-manage-workspace-uploads-details' container direction="column" alignItems='start' justifyContent="start">
            { curCollection && curCollection.uploads.map((item, idx) =>
              <Card id={"collection-upload-item-"+item.name} key={'collection-upload-item'+idx} variant="outlined" 
                    data-active={uploadSelectionIndex === idx ? '' : undefined}
                    sx={{minWidth:'100%', backgroundColor:'#D3DEE6', borderRadius:'10px', 
                          '&:hover':{backgroundColor:'rgba(0, 0, 0, 0.25)'},
                          '&[data-active]': {borderColor:'rgba(155, 175, 202, 0.85)',backgroundColor:'#BAC6CD'},
                          '&[data-active]:hover': { backgroundColor:'rgba(0, 0, 0, 0.25)' },
                        }}
              >
                <CardHeader title={
                                  <Grid id="collection-card-header-wrapper" container direction="row" alignItems="start" justifyContent="start" wrap="nowrap">
                                    <Grid>
                                      <Typography gutterBottom variant="h6" component="h4" noWrap>
                                        {item.name}
                                      </Typography>
                                    </Grid>
                                    <Grid sx={{marginLeft:'auto'}}>
                                      <Tooltip title="Edit this upload">
                                        <IconButton aria-label="Edit this upload" onClick={() => handleUploadEdit(curCollection.id, item.key)}>
                                          <BorderColorOutlinedIcon fontSize="small"/>
                                        </IconButton>
                                      </Tooltip>
                                    </Grid>
                                  </Grid>
                                  }
                              style={{paddingBottom:'0px'}}
                />
                <CardContent sx={{paddingTop:'0px'}}>
                  <Accordion expanded={expandedUpload === 'upload-details-'+item.name}
                             onChange={handleExpandedChange('upload-details-'+item.name)}
                             sx={{backgroundColor:'#BFCBE1'}}>
                    <AccordionSummary
                      id={'summary-'+item.name}
                      expandIcon={<ExpandMoreIcon />}
                      aria-controls={`upload-details-content-${item.name}`}
                    >
                      <Typography component="span">
                        Advanced details
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails id={`upload-details-content-${item.name}`} sx={{backgroundColor:'#C8D2E4'}}>
                      <Grid container id={'collection-upload-'+item.name} direction="column" alignItems="start" justifyContent="start">
                        <Grid sx={{padding:'5px 0', width:'100%'}}>
                          <Grid container direction="row" alignItems="start" justifyContent="space-between">
                            <Typography variant="body2">
                              {item.imagesWithSpeciesCount + '/' + item.imagesCount + ' images tagged with species'}
                            </Typography>
                            <IconButton onClick={() => handleUploadDetailsEdit(curCollection.id, item)} sx={{marginLeft:'auto'}}>
                              <EditNoteOutlinedIcon fontSize="small" />
                            </IconButton>
                          </Grid>
                        </Grid>
                        <Grid sx={{padding:'5px 0'}}>
                          <Typography variant="body2">
                            {item.description}
                          </Typography>
                        </Grid>
                        <Grid sx={{padding:'5px 0'}}>
                          <Typography variant="body2" sx={{fontStyle:'italic'}}>
                            Uploaded folder{item.folders.length > 1 ? 's' : ''}:
                          </Typography>
                          <Typography variant="body2" sx={{wordWrap:'break-word', wordBreak:'break-all'}}>
                            {item.folders.join(", ")}
                          </Typography>
                        </Grid>
                        <Grid>
                          <Typography variant="body2" sx={{fontWeight:'500'}}>
                            Edits
                          </Typography>
                        </Grid>
                      </Grid>
                      <Box sx={{border:"1px solid black", width:'100%', minHeight:'4em', maxHeight:'4em', overflow:"scroll"}} >
                        {item.edits.map((editItem, idx) =>
                          <Typography variant="body2" key={"collection-upload-edits-" + idx} sx={{padding:"0 5px"}} >
                            {editItem}
                          </Typography>
                        )}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </CardContent>
              </Card>
            )}
          </Grid>
        </div>
      </Grid>
      { uploadDetailEdit &&
          <EditUploadDetails upload={uploadDetailEdit.upload}
                            onChange={handleUploadDetailChange}
                            onClose={() => setUploadDetailEdit(null)}
          />
      }
      { loadingCollections && 
          <WorkspaceOverlay>
            <Typography gutterBottom variant="body2" color="lightgrey">
              Loading collections, please wait...
            </Typography>
            <CircularProgress variant="indeterminate" />
            <Typography gutterBottom variant="body2" color="lightgrey">
              This may take a while
            </Typography>
          </WorkspaceOverlay>
      }
      { editingUploadMask && 
          <WorkspaceOverlay>
              <Typography gutterBottom variant="body2" color="lightgrey">
                Preparing to edit uploaded images
              </Typography>
              <CircularProgress variant="indeterminate" />
              <Button size="small" variant="contained" onClick={() => setEditingUploadMask(false)} sx={{marginTop:'10px'}}>
                Cancel
              </Button>
          </WorkspaceOverlay>
      }
      { pendingMessage && 
          <WorkspaceOverlay>
              <Typography gutterBottom variant="body2" color="lightgrey">
                {pendingMessage}
              </Typography>
              <CircularProgress variant="indeterminate" />
          </WorkspaceOverlay>
      }
    </Box>
  );
}

CollectionsManage.propTypes = {
  loadingCollections:     PropTypes.bool.isRequired,
  selectedCollection:     PropTypes.string,
  onSelectionChange:      PropTypes.func.isRequired,
  onEditUpload:           PropTypes.func.isRequired,
  searchSetup:            PropTypes.func.isRequired,
  onUploadUpdateMetadata: PropTypes.func.isRequired,
};

CollectionsManage.defaultProps = {
  selectedCollection: null,
};
