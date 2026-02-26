'use client'

/** @module LandingUQuery */

import * as React from 'react';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid';
import PriorityHighOutlinedIcon from '@mui/icons-material/PriorityHighOutlined';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Stack from '@mui/material/Stack';
import { useTheme } from '@mui/material/styles';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import LandingInfoTile from './LandingInfoTile';
import { BaseURLContext, TokenExpiredFuncContext, TokenContext } from '../serverInfo';

/**
 * Returns the UI for queries on the Landing page
 * @function
 * @returns {object} The rendered UI
 */
export default function LandingQuery() {
  const theme = useTheme();
  const setTokenExpired = React.useContext(TokenExpiredFuncContext);
  const serverURL = React.useContext(BaseURLContext);
  const queryToken = React.useContext(TokenContext);
  const [animalsNums,setAnimalsNums] = React.useState(null);

  /**
   * Retreives the species stats from the server
   * @function
   */
  const getSpeciesStats = React.useCallback(() => {
    const speciesStatsUrl = serverURL + '/speciesStats?t=' + encodeURIComponent(queryToken);

    try {
      const resp = fetch(speciesStatsUrl, {
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
              throw new Error(`Failed to get species statistics: ${resp.status}`, {cause:resp});
            }
          })
        .then((respData) => {
            // Process the results
          setAnimalsNums(respData);
        })
        .catch(function(err) {
          console.log('Species Statistics Error: ',err);
        });
    } catch (error) {
      console.log('Species Statistics Unknown Error: ',err);
    }
  }, [serverURL, setAnimalsNums, queryToken]);

  // Get the statistics to show
  React.useLayoutEffect(() => {
    if (animalsNums === null) {
      getSpeciesStats();
    }
  }, [animalsNums, setAnimalsNums]);

  // TODO: Make animalsNums load from server
  const showAnimalIdx = React.useMemo(() => {
    if (animalsNums === null) {
      return null;
    }

    let foundIdx = [Math.floor(Math.random() * animalsNums.length),
                    Math.floor(Math.random() * animalsNums.length),
                    Math.floor(Math.random() * animalsNums.length)];
    let fixed = 0;
    while (fixed < 5) {
      let fixedValue = false;
      for (let idx = 1; idx < foundIdx.length; idx++) {
        const found = foundIdx.filter((item) => item === foundIdx[idx]);
        if (found.length > 1) {
          // We have a duplicate
          foundIdx[idx] = Math.floor(Math.random() * animalsNums.length);
          fixedValue = true;
        }
      }

      if (fixedValue === true) {
        fixed++;
      } else {
        break;
      }
    }

    return foundIdx;
  }, [animalsNums]);

  // Render the UI
  return (
    <Stack>
      <Grid id="sandbox-query-info-wrapper" container direction="row" alignItems="center" justifyContent="space-around"
            sx={{paddingTop:'10px'}}>
        { animalsNums?.map((item, idx) =>  showAnimalIdx?.includes(idx) && <LandingInfoTile key={idx} title={item[1]} details={item[0]} />
        )
      }
      </Grid>
    </Stack>
  );
}
