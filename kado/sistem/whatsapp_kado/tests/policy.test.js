const {test} = require('node:test');
const assert = require('node:assert/strict');
const {eligible} = require('../policy');
const incoming = {fromMe: false, isStatus: false, from: '905551112233@c.us', timestamp: 110, type: 'chat'};
test('new direct text and voice messages accepted', () => {
    assert.equal(eligible(incoming, 100, 'all', ''), true);
    assert.equal(eligible({...incoming, type: 'ptt', from: '123@lid'}, 100, 'all', ''), true);
});
test('groups, status, self, history and documents excluded', () => {
    for (const change of [{from: '123@g.us'}, {from: 'status@broadcast'}, {isStatus: true},
        {fromMe: true}, {timestamp: 99}, {type: 'document'}, {type: 'image'}]) {
        assert.equal(eligible({...incoming, ...change}, 100, 'all', ''), false);
    }
});
test('test mode excludes other customers', () => {
    assert.equal(eligible(incoming, 100, 'test', '905551112233'), true);
    assert.equal(eligible(incoming, 100, 'test', '905559999999'), false);
});
