'use client'

/** @module landing/LandingUpload */

import * as React from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Radio from '@mui/material/Radio';
import Stack from '@mui/material/Stack';
import { useTheme } from '@mui/material/styles';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import IncompleteUploadItem from './IncompleteUploadItem';
import LandingInfoTile from './LandingInfoTile';
import { BaseURLContext, CollectionsInfoContext, TokenExpiredFuncContext, MobileDeviceContext, 
         SandboxInfoContext, TokenContext, UserNameContext } from '../serverInfo';

/**
 * Returns the UI for uploads on the Landing page
 * @function
 * @param {boolean} loadingSandbox Set to true when the sandbox information is getting loaded
 * @param {function} onChange Function to call when a new upload is selected
 * @returns {object} The rendered UI
 */
export default function LandingUpload({loadingSandbox, onChange}) {
  const theme = useTheme();
  const curSandboxInfo = React.useContext(SandboxInfoContext);
  const mobileDevice = React.useContext(MobileDeviceContext);
  const setTokenExpired = React.useContext(TokenExpiredFuncContext);
  const serverURL = React.useContext(BaseURLContext);
  const uploadToken = React.useContext(TokenContext);
  const userName = React.useContext(UserNameContext);
  const [numPrevUploads, setNumPrevUploads] = React.useState(null);

  const sandboxItems = curSandboxInfo;

  /**
   * Retreives the upload stats from the server
   * @function
   */
  const getUploadStats = React.useCallback(() => {
    const uploadStatsUrl = serverURL + '/sandboxStats?t=' + encodeURIComponent(uploadToken);

    try {
      const resp = fetch(uploadStatsUrl, {
          credentials: 'include',
          method: 'GET',
        }).then(async (resp) => {
            if (resp.ok) {
              return resp.json();
            } else {
              if (resp.status === 401) {
                // User needs to log in again
                setTokenExpired();
              }
              throw new Error(`Failed to get upload statistics: ${resp.status}`, {cause:resp});
            }
          })
        .then((respData) => {
            // Process the results
          setNumPrevUploads(respData);
        })
        .catch(function(err) {
          console.log('Upload Statistics Error: ',err);
        });
    } catch (error) {
      console.log('Upload Statistics Unknown Error: ',err);
    }
  }, [serverURL, setNumPrevUploads, uploadToken]);

  // Get the statistics to show
  React.useLayoutEffect(() => {
    if (numPrevUploads === null) {
      getUploadStats();
    }
  }, [numPrevUploads, setNumPrevUploads]);

  // Determine if we have unfinished uploads
  const unfinished = React.useMemo(() => {
    let found = null;
    if (sandboxItems && sandboxItems.length > 0) {
      for (let oneItem of sandboxItems) {
        if (oneItem && oneItem.uploads && oneItem.uploads.length > 0) {
          for (let oneUp of oneItem.uploads) {
            if (oneUp && oneUp.uploadCompleted !== undefined) {
              if (oneUp.uploadCompleted === false) {
                found = oneItem;
                break;
              }
            }
          }
        }
        if (found !== null) {
          break;
        }
      }
    }
    return found !== null;
  }, [sandboxItems]);

  /**
   * Handle the user wanting to repair a sandbox item
   * @function
   * @param {object} sandboxItem The sandbox item of the upload
   * @param {object} uploadItem The upload item to repair
   */
  const handleRepairUpload = React.useCallback((sandboxItem, uploadItem) => {
    onChange(sandboxItem, uploadItem);
  }, []);

  // Render the UI
  return (
    <Stack>
      { unfinished || loadingSandbox  ? (
        <React.Fragment>
          <Grid id="sandbox-status-wrapper" container direction="row" alignItems="sflex-tart" justifyContent="flex-start">
            <Grid size={{sm:4, md:4, lg:4}} sx={{left:'auto'}}>
              <Typography gutterBottom sx={{ ...theme.palette.landing_upload_prompt,
                          visibility: !loadingSandbox?"visible":"hidden" }} >
                Unfinished uploads
              </Typography>
            </Grid>
            <Grid size={{sm:4, md:4, lg:4}}>
              <Typography gutterBottom sx={{ ...theme.palette.landing_upload_refresh,
                          visibility: loadingSandbox?"visible":"hidden" }} >
                Refreshing...
              </Typography>
            </Grid>
            <Grid size={{sm:4, md:4, lg:4}}>
              &nbsp;
            </Grid>
          </Grid>
          <Grid id="sandbox-upload-item-wrapper" container direction="row" alignItems="start" justifyContent="start"
                sx={{ ...theme.palette.landing_upload, padding:'0px 0px', minHeight:'40px', maxHeight:'120px'}} >
            { sandboxItems?.map((item, idx) => {
                let curRow = 0;
                const incompleteUploads = item.uploads.filter((item) => item.uploadCompleted === false);
                return incompleteUploads.map((upItem, upIdx) => {
                    curRow += 1;
                    return (<IncompleteUploadItem key={`${idx}-${upIdx}`}
                                                  upload={upItem}
                                                  collection={item}
                                                  highlight={curRow & 0x01 === 0}
                                                  onRepair={handleRepairUpload}
                            />
                            );
                })
              })
            }
          </Grid>
        </React.Fragment>
        )
        : mobileDevice ? <Box>Nothing to do</Box>
            : <Typography gutterBottom sx={{ color: 'text.secondary', fontSize: 14, textAlign: 'center',  }} >
                No incomplete uploads found
              </Typography>
      }
      <Grid id="sandbox-upload-info-wrapper" container direction="row" alignItems="center" justifyContent="space-around"
            sx={{paddingTop:'10px'}}>
        <Typography variant="body2" >
          If you think you have an incomplete upload that's not shown, contact your administrator
        </Typography>
      </Grid>
      <Grid id="sandbox-upload-info-wrapper" container direction="row" alignItems="center" justifyContent="space-around"
            sx={{paddingTop:'30px'}}>
        { numPrevUploads?.map((item, idx) => {
            return <LandingInfoTile key={idx} title={item[1]} details={item[0]} />
          })
        }
      </Grid>
    </Stack>
  );
}
