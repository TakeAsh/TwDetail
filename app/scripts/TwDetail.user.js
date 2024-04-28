// ==UserScript==
// @name         TwDetail
// @namespace    https://www.TakeAsh.net/
// @version      2024-04-28_18:31
// @description  Enhance twitter
// @author       TakeAsh
// @match        https://twitter.com/*
// @match        https://*.twitter.com/*
// @match        https://x.com/*
// @match        https://*.x.com/*
// @require      https://raw.githubusercontent.com/TakeAsh/js-Modules/main/modules/PrepareElement.js
// @icon         https://www.google.com/s2/favicons?sz=64&domain=twitter.com
// @grant        none
// ==/UserScript==

(async (w, d) => {
  'use strict';
  const keyStorage = 'TwDetail';
  //initConf('https://api.example.com/', 'my_name', 'my_password');
  if (!localStorage[keyStorage]) {
    console.error('config not saved')
    return;
  }
  const conf = JSON.parse(localStorage[keyStorage]);
  //console.log(conf);
  const regStatusId = /\/status\/(?<id>\d+)/;
  const details = {};
  await sleep(5 * 1000);
  addStyle({
    '.buttonTwDetail': {
      margin: '0em 0em 0em 0.4em',
    },
  })
  const target = getNodesByXpath('//section[@role="region"]/div/div')[0];
  if (!target) {
    console.log('No target');
    return;
  }
  checkStatuses(target);
  const observer = new MutationObserver(
    (mutations) => mutations.forEach(
      (mutation) => checkStatuses(mutation.target)));
  observer.observe(target, { childList: true, subtree: true, });

  function initConf(uriApi, username, password) {
    localStorage[keyStorage] = JSON.stringify({
      uriApi: uriApi,
      credential: {
        username: username,
        password: password,
      },
    });
  }

  async function checkStatuses(node) {
    const links = getNodesByXpath('.//a[time and not(@data-twd)]', node)
      .map((a) => { a.dataset.twd = toStatusId(a); return a; });
    const linkHash = links.reduce(
      (acc, cur) => {
        if (cur.dataset.twd) {
          acc[cur.dataset.twd] = 1;
        }
        return acc;
      },
      {}
    );
    const linkIds = Object.keys(linkHash)
      .filter(id => !details.hasOwnProperty(id));
    if (linkIds.length) {
      //console.log({ links: links, linkIds: linkIds });
      const subDetails = await getDetails(linkIds);
      if (subDetails) {
        Object.assign(details, subDetails);
      } else {
        node.insertBefore(prepareElement(
          {
            tag: 'div',
            textContent: 'Failed to login TwDetail',
            style: { color: '#ff0000', },
          }),
          node.firstChild
        );
        return;
      }
    }
    links.forEach((a) => {
      if (!a.dataset || !a.dataset.twd || !details[a.dataset.twd]) {
        return;
      }
      const detail = details[a.dataset.twd]
      if (detail.text) {
        const media = detail.medias
          ? { key: detail.medias[0].shorten, urls: detail.medias.map(m => m.url).join('\n') }
          : { key: '', urls: '' };
        const urls = detail.urls
          ? JSON.stringify(detail.urls)
          : '';
        a.parentNode.appendChild(prepareElement({
          tag: 'button',
          classes: ['buttonTwDetail'],
          dataset: {
            id: a.dataset.twd,
            userName: detail.user.name,
            userScreenName: detail.user.screen_name,
            text: detail.text,
            urls: urls,
            mediaKey: media.key,
            mediaUrls: media.urls,
          },
          textContent: 'Copy',
          title: detail.text,
          events: { click: copyText, },
        }));
      }
      if (detail.medias) {
        detail.medias.forEach((media, i) => {
          const index = String.fromCodePoint(0x61 + i);
          a.parentNode.appendChild(prepareElement({
            tag: 'button',
            classes: ['buttonTwDetail'],
            dataset: {
              id: a.dataset.twd,
              index: index,
              url: media.url,
              ext: media.ext
            },
            textContent: index,
            title: `${media.type}/${media.ext}`,
            events: { click: downloadMedia, },
          }));
        });
      }
    });
  }

  async function getDetails(linkIds) {
    const session = await getSession() || await login();
    if (!session) {
      console.log('Failed to login TwDetail');
      return null;
    }
    sessionStorage[keyStorage] = JSON.stringify(session);
    const response = await fetch(`${conf.uriApi}tweet/details`, {
      method: 'POST',
      mode: 'cors',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(linkIds),
    });
    const result = await response.json();
    if (!result) {
      console.log(`Failed to fetch at 'getDetails'`);
      return null;
    } else if (result.detail) {
      console.log(`${result.detail} at 'getDetails'`);
      return null;
    } else if (result.success) {
      console.log(`${result.success} at 'getDetails'`);
      return null;
    }
    return result;
  }

  async function getSession() {
    const options = {
      method: 'GET',
      mode: 'cors',
      credentials: 'include',
    };
    const session = JSON.parse(sessionStorage[keyStorage] || '{}');
    if ((session.expire || 0) <= Date.now()) { return null }
    if (session.access_token) {
      options.headers = { Authorization: `Bearer ${session.access_token}` };
    }
    try {
      const response = await fetch(conf.uriApi, options);
      const result = await response.json();
      if (!response.ok) {
        console.log(result);
        return null;
      }
      return result;
    } catch (ex) {
      console.log(`${ex.message} at 'getToken'`);
      return null;
    }
  }

  async function login() {
    const data = new FormData();
    Object.keys(conf.credential)
      .forEach(key => data.append(key, conf.credential[key]));
    try {
      const response = await fetch(`${conf.uriApi}token`, {
        method: 'POST',
        mode: 'cors',
        credentials: 'include',
        body: data,
      });
      const result = await response.json();
      if (!response.ok) {
        console.log(result);
        return null;
      }
      return result;
    } catch (ex) {
      console.log(`${ex.message} at 'login'`);
      return null;
    }
  }

  function toStatusId(link) {
    const m = regStatusId.exec(link.href);
    return m && m.groups.id ? m.groups.id : null;
  }

  async function downloadMedia(event) {
    const info = event.target.dataset;
    const response = await fetch(info.url, {
      mode: 'cors',
    });
    const blob = await response.blob();
    const dataUrl = URL.createObjectURL(blob);
    const link = prepareElement({
      tag: 'a',
      download: `${info.id}${info.index}.${info.ext}`,
      href: dataUrl,
    });
    link.click();
    URL.revokeObjectURL(dataUrl);
  }

  function copyText(event) {
    const info = event.target.dataset;
    let text = !info.mediaKey
      ? info.text
      : info.text.replace(info.mediaKey, `\n${info.mediaUrls}`);
    if (info.urls) {
      const urls = JSON.parse(info.urls);
      Object.keys(urls).forEach(url => { text = text.replaceAll(url, urls[url]) });
    }
    const full_text = `${info.userName} @${info.userScreenName}\n${text}\nhttps://twitter.com/${info.userScreenName}/status/${info.id}\n`;
    navigator.permissions.query({ name: 'clipboard-write' })
      .then((result) => {
        if (result.state === 'granted' || result.state === 'prompt') {
          navigator.clipboard.writeText(full_text)
            .then(
              () => { console.log('write clipboard success') },
              () => { console.log('write clipboard failed'); }
            );
        }
      });
  }

  function getNodesByXpath(xpath, context) {
    const itr = d.evaluate(
      xpath,
      context || d,
      null,
      XPathResult.ORDERED_NODE_ITERATOR_TYPE,
      null
    );
    const nodes = [];
    let node = null;
    while (node = itr.iterateNext()) {
      nodes.push(node);
    }
    return nodes;
  }

  function sleep(msec) {
    return new Promise((resolve) => setTimeout(resolve, msec));
  }
})(window, document)