'use client'

/** @module components/CollectionUploadTile */

import * as React from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import BorderColorOutlinedIcon from '@mui/icons-material/BorderColorOutlined';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import EditNoteOutlinedIcon from '@mui/icons-material/EditNoteOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

/**
 * Returns the UI for a collection upload
 * @function
 * @param {string} collectionId The ID of the collection this upload belongs to
 * @param {object} upload The upload to display
 * @param {string} key The item key
 * @param {boolean} active This tile is active when set to true
 * @param {boolean} expanded The details are expanded when set to true
 * @param {function} onUploadEdit Function to call when the upload is to be edited
 * @param {function} onExpandChange Function to call when the use expands or collapses the details
 * @param {function} [onEditDetails] When not null, enables editing upload details and is called if the user wants to edit details
 */
export default function CollectionUploadTile({collectionId, upload, active, expanded, onUploadEdit, onExpandChange, onEditDetails}) {
  return (
    <Card id={"collection-upload-item-"+upload.name} variant="outlined" 
          data-active={active ? '' : undefined}
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
                              {upload.name}
                            </Typography>
                          </Grid>
                          <Grid sx={{marginLeft:'auto'}}>
                            <Tooltip title="Edit this upload">
                              <IconButton aria-label="Edit this upload" onClick={onUploadEdit}>
                                <BorderColorOutlinedIcon fontSize="small"/>
                              </IconButton>
                            </Tooltip>
                          </Grid>
                        </Grid>
                        }
                    style={{paddingBottom:'0px'}}
      />
      <CardContent sx={{paddingTop:'0px'}}>
        <Accordion expanded={expanded}
                   onChange={onExpandChange}
                   sx={{backgroundColor:'#BFCBE1'}}>
          <AccordionSummary
            id={'summary-'+upload.name}
            expandIcon={<ExpandMoreIcon />}
            aria-controls={`upload-details-content-${upload.name}`}
          >
            <Typography component="span">
              Advanced details
            </Typography>
          </AccordionSummary>
          <AccordionDetails id={`upload-details-content-${upload.name}`} sx={{backgroundColor:'#C8D2E4'}}>
            <Grid container id={'collection-upload-'+upload.name} direction="column" alignItems="start" justifyContent="start">
              <Grid sx={{padding:'5px 0', width:'100%'}}>
                <Grid container direction="row" alignItems="start" justifyContent="space-between">
                  <Typography variant="body2">
                    {upload.imagesWithSpeciesCount + '/' + upload.imagesCount + ' images tagged with species'}
                  </Typography>
                  { onEditDetails &&
                        <IconButton onClick={onEditDetails} sx={{marginLeft:'auto'}}>
                          <EditNoteOutlinedIcon fontSize="small" />
                        </IconButton>
                  }
                </Grid>
              </Grid>
              <Grid sx={{padding:'5px 0'}}>
                <Typography variant="body2">
                  {upload.description}
                </Typography>
              </Grid>
              <Grid sx={{padding:'5px 0'}}>
                <Typography variant="body2" sx={{fontStyle:'italic'}}>
                  Uploaded folder{upload.folders.length > 1 ? 's' : ''}:
                </Typography>
                <Typography variant="body2" sx={{wordWrap:'break-word', wordBreak:'break-all'}}>
                  {upload.folders.join(", ")}
                </Typography>
              </Grid>
              <Grid>
                <Typography variant="body2" sx={{fontWeight:'500'}}>
                  Edits
                </Typography>
              </Grid>
            </Grid>
            <Box sx={{border:"1px solid black", width:'100%', minHeight:'4em', maxHeight:'4em', overflow:"scroll"}} >
              {upload.edits.map((editItem, idx) =>
                <Typography variant="body2" key={"collection-upload-edits-" + idx} sx={{padding:"0 5px"}} >
                  {editItem}
                </Typography>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
    )
};
